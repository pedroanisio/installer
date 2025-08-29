#!/usr/bin/env python3
"""
Additional tests for installer module to improve coverage
"""

import pytest
import os
import sys
import stat
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

# Add the parent directory to the path to import our module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.installer.installer import UniversalInstaller
from src.installer.exceptions import ValidationError, PermissionError, InstallationError


class TestInstallerEdgeCases:
    """Test edge cases and error paths in installer"""
    
    def test_is_symlink_or_hardlink_oserror(self, tmp_path):
        """Test symlink check when file doesn't exist"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        # Non-existent file should return False
        assert not installer.is_symlink_or_hardlink(Path("/nonexistent/file"))
    
    def test_is_python_script_by_extension(self, tmp_path):
        """Test Python script detection by .pyw extension"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        # Test .pyw extension
        pyw_file = tmp_path / "script.pyw"
        pyw_file.write_text("print('hello')")
        assert installer.is_python_script(pyw_file)
    
    def test_is_python_script_unreadable(self, tmp_path):
        """Test Python script detection when file can't be read"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        script = tmp_path / "script"
        script.write_text("#!/usr/bin/env python3\nprint('hello')")
        
        # Mock open to raise OSError
        with patch('builtins.open', side_effect=OSError("Can't read")):
            assert not installer.is_python_script(script)
    
    def test_ensure_shebang_non_python(self, tmp_path):
        """Test ensure_shebang with non-Python shebang"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        script = tmp_path / "script.py"
        script.write_text("#!/bin/bash\necho 'hello'")
        
        with patch('builtins.print') as mock_print:
            content = installer.ensure_shebang(script)
        
        # Should warn about non-Python shebang
        assert any("non-Python shebang" in str(call) for call in mock_print.call_args_list)
        assert content.startswith("#!/bin/bash")
    
    def test_validate_source_not_file(self, tmp_path):
        """Test validate_source with directory"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        # Create a directory
        dir_path = tmp_path / "mydir"
        dir_path.mkdir()
        
        with pytest.raises(ValidationError, match="symlink or hardlink"):
            installer.validate_source(dir_path)
    
    def test_validate_source_hardlink(self, tmp_path):
        """Test validate_source with hardlink"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        # Create a file and a hardlink
        original = tmp_path / "original.py"
        original.write_text("#!/usr/bin/env python3\nprint('hello')")
        
        # Mock the hardlink check
        with patch.object(installer, 'is_symlink_or_hardlink', return_value=True):
            with pytest.raises(ValidationError, match="symlink or hardlink"):
                installer.validate_source(original)
    
    def test_create_install_dir_no_write_permission(self, tmp_path):
        """Test create_install_dir when directory exists but no write permission"""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o555)
        
        installer = UniversalInstaller(str(readonly_dir))
        
        try:
            with pytest.raises(PermissionError, match="No write permission"):
                installer.create_install_dir()
        finally:
            readonly_dir.chmod(0o755)
    
    def test_create_install_dir_other_oserror(self, tmp_path):
        """Test create_install_dir with other OS errors"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        with patch('pathlib.Path.mkdir', side_effect=OSError(99, "Other error")):
            with pytest.raises(InstallationError, match="Failed to create directory"):
                installer.create_install_dir()
    
    def test_verify_installation_symlink_check(self, tmp_path):
        """Test verify_installation detects if target became symlink"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        # Create a symlink with executable permissions
        target = tmp_path / "target"
        original = tmp_path / "original"
        original.write_text("content")
        original.chmod(0o755)
        target.symlink_to(original)
        
        with pytest.raises(ValidationError, match="became a symlink"):
            installer.verify_installation(target)
    
    def test_verify_installation_nonexistent(self, tmp_path):
        """Test verify_installation with non-existent file"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        # Try to verify a non-existent file
        target = tmp_path / "nonexistent"
        
        with pytest.raises(ValidationError, match="does not exist"):
            installer.verify_installation(target)
    
    def test_install_file_invalid_target_filename(self, tmp_path):
        """Test install_file with invalid target filename"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        source = tmp_path / "source.py"
        source.write_text("#!/usr/bin/env python3\nprint('hello')")
        
        # Test with path separator in target name
        result = installer.install_file(source, target_name="../../evil")
        assert not result
    
    def test_install_file_unexpected_error(self, tmp_path):
        """Test install_file with unexpected error"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        source = tmp_path / "source.py"
        source.write_text("#!/usr/bin/env python3\nprint('hello')")
        
        # Mock validate_source to raise unexpected error
        with patch.object(installer, 'validate_source', side_effect=RuntimeError("Unexpected")):
            result = installer.install_file(source)
            assert not result
    
    def test_uninstall_file_invalid_filename(self, tmp_path):
        """Test uninstall_file with invalid filename"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        # Test with path traversal attempt
        result = installer.uninstall_file("../../../etc/passwd")
        assert not result
    
    def test_uninstall_file_validation_error(self, tmp_path):
        """Test uninstall_file when validation fails"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        with patch.object(installer, 'validate_target_path', side_effect=ValidationError("Invalid")):
            result = installer.uninstall_file("myfile")
            assert not result
    
    def test_uninstall_file_oserror(self, tmp_path):
        """Test uninstall_file with OS error during removal"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        installer.create_install_dir()
        
        target = installer.install_dir / "myfile"
        target.write_text("content")
        
        with patch('builtins.input', return_value='y'):
            with patch.object(Path, 'unlink', side_effect=OSError("Can't delete")):
                result = installer.uninstall_file("myfile")
                assert not result
    
    def test_install_self_file_not_found(self, tmp_path):
        """Test install_self when script file not found"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        with patch('pathlib.Path.exists', return_value=False):
            result = installer.install_self()
            assert not result
    
    def test_install_self_exception(self, tmp_path):
        """Test install_self with general exception"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        with patch.object(installer, 'install_file', side_effect=Exception("Error")):
            result = installer.install_self()
            assert not result


class TestInstallerNonExecutable:
    """Test handling of non-executable files"""
    
    def test_validate_source_non_executable(self, tmp_path, capsys):
        """Test warning for non-executable binary"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        # Create non-executable file
        binary = tmp_path / "mybinary"
        binary.write_bytes(b"\x7fELF")  # ELF header
        binary.chmod(0o644)  # Not executable
        
        installer.validate_source(binary)
        
        captured = capsys.readouterr()
        assert "not currently executable" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
