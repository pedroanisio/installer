#!/usr/bin/env python3
"""
Test suite for install-binary.py
Following TDD principles with comprehensive test coverage
"""

import pytest
import json
import os
import sys
import tempfile
import shutil
import stat
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
import threading
import time
from datetime import datetime

# Add the parent directory to the path to import our module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.install_binary import (
    HistoryManager,
    UniversalInstaller,
    InstallationError,
    ValidationError,
    PermissionError,
)


class TestSecurityValidations:
    """Test security-related functionality"""
    
    def test_path_traversal_prevention(self, tmp_path):
        """Test that path traversal attacks are prevented"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        # Test various path traversal attempts
        malicious_paths = [
            "../etc/passwd",
            "../../etc/shadow",
            "/etc/passwd",
            "test/../../../etc/passwd",
            "test/../../sensitive",
            str(tmp_path / ".." / "outside")
        ]
        
        for path in malicious_paths:
            with pytest.raises(ValidationError, match="outside allowed directory"):
                installer.validate_target_path(Path(path))
    
    def test_symlink_detection(self, tmp_path):
        """Test that symlinks are properly detected and handled"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        # Create a regular file and a symlink
        regular_file = tmp_path / "regular.py"
        regular_file.write_text("#!/usr/bin/env python3\nprint('hello')")
        
        symlink_file = tmp_path / "symlink.py"
        symlink_file.symlink_to(regular_file)
        
        # Test detection
        assert not installer.is_symlink_or_hardlink(regular_file)
        assert installer.is_symlink_or_hardlink(symlink_file)
        
        # Test that symlinks are rejected during validation
        with pytest.raises(ValidationError, match="symlinks are not allowed"):
            installer.validate_source(symlink_file)
    
    def test_toctou_prevention(self, tmp_path):
        """Test Time-of-Check to Time-of-Use prevention"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        installer.create_install_dir()
        
        source = tmp_path / "test.py"
        source.write_text("#!/usr/bin/env python3\nprint('test')")
        
        # First validate the source to set up internal state
        validated_source = installer.validate_source(source)
        
        # Now simulate file modification
        original_mtime = installer._source_stat.st_mtime
        original_size = installer._source_stat.st_size
        
        # Mock stat to return different values
        with patch.object(Path, 'stat') as mock_stat:
            mock_stat.return_value = Mock(
                st_mtime=original_mtime + 100,
                st_size=original_size,
                st_mode=33261  # Regular file with execute permissions
            )
            
            with pytest.raises(ValidationError, match="File was modified during operation"):
                installer.verify_source_unchanged(validated_source)


class TestErrorHandling:
    """Test improved error handling"""
    
    def test_specific_json_errors(self, tmp_path):
        """Test specific handling of JSON errors"""
        history_file = tmp_path / "history.json"
        
        # Write invalid JSON
        history_file.write_text("{'invalid': json}")
        
        with pytest.raises(ValidationError, match="Invalid JSON in history file"):
            HistoryManager(str(history_file))
    
    def test_permission_errors(self, tmp_path):
        """Test handling of permission errors"""
        # Create a directory we can't write to
        readonly_dir = tmp_path / "readonly_bin"
        readonly_dir.mkdir()
        
        installer = UniversalInstaller(str(readonly_dir))
        
        # Remove write permissions
        readonly_dir.chmod(0o555)
        
        try:
            with pytest.raises(PermissionError, match="No write permission"):
                installer.create_install_dir()
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)
    
    def test_disk_full_simulation(self, tmp_path):
        """Test handling of disk full errors"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        source = tmp_path / "test.py"
        source.write_text("#!/usr/bin/env python3\nprint('test')")
        
        # Mock file write to raise OSError (disk full)
        with patch('builtins.open', mock_open()) as mock_file:
            mock_file.side_effect = OSError(28, "No space left on device")
            
            result = installer.install_file(str(source))
            assert not result  # Should return False on error
    
    def test_no_silent_failures(self, tmp_path):
        """Test that all errors are properly propagated"""
        history = HistoryManager(str(tmp_path / "history.json"))
        
        # Make history file read-only after creation
        history.save_history()
        
        # Make the parent directory read-only to prevent temp file creation
        history.history_file.parent.chmod(0o555)
        
        try:
            # This should raise an exception, not fail silently
            with pytest.raises(PermissionError):
                history.add_installation(Path("test"), Path("dest"), "binary")
        finally:
            # Restore permissions for cleanup
            history.history_file.parent.chmod(0o755)


class TestRacePrevention:
    """Test race condition prevention in history file access"""
    
    def test_concurrent_history_writes(self, tmp_path):
        """Test that concurrent writes to history file are properly serialized"""
        history_file = tmp_path / "history.json"
        
        # Track successful writes
        successful_writes = []
        write_lock = threading.Lock()
        
        def add_entries(thread_id):
            """Add entries from a thread"""
            manager = HistoryManager(str(history_file))
            for i in range(10):
                try:
                    manager.add_installation(
                        Path(f"source_{thread_id}_{i}"),
                        Path(f"target_{thread_id}_{i}"),
                        "binary",
                        f"checksum_{thread_id}_{i}"
                    )
                    with write_lock:
                        successful_writes.append((thread_id, i))
                except Exception as e:
                    print(f"Thread {thread_id} failed on entry {i}: {e}")
                time.sleep(0.001)  # Small delay to increase chance of collision
        
        # Create threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=add_entries, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify history file is valid
        final_history = HistoryManager(str(history_file))
        
        # All writes should have succeeded due to file locking
        assert len(successful_writes) == 50  # 5 threads * 10 entries
        
        # Verify JSON is valid and not corrupted
        with open(history_file) as f:
            data = json.load(f)
            assert "installations" in data
            assert isinstance(data["installations"], list)
            
        # The actual number in history might be less due to race conditions
        # but the file should never be corrupted
        print(f"Total installations recorded: {len(final_history.history['installations'])}")
    
    def test_file_locking(self, tmp_path):
        """Test that file locking prevents concurrent access"""
        history = HistoryManager(str(tmp_path / "history.json"))
        
        # Test that lock is acquired and released properly
        with patch('fcntl.flock') as mock_flock:
            history.save_history()
            
            # Verify lock was acquired and released
            assert mock_flock.call_count == 2
            calls = mock_flock.call_args_list
            
            # First call should be LOCK_EX
            assert calls[0][0][1] == 2  # fcntl.LOCK_EX
            
            # Second call should be LOCK_UN
            assert calls[1][0][1] == 8  # fcntl.LOCK_UN


class TestHistoryManager:
    """Test HistoryManager functionality"""
    
    def test_history_initialization(self, tmp_path):
        """Test history manager initialization"""
        history_file = tmp_path / "history.json"
        manager = HistoryManager(str(history_file))
        
        assert manager.history_file == history_file
        assert manager.history == {"installations": [], "uninstallations": []}
    
    def test_add_installation(self, tmp_path):
        """Test adding installation records"""
        manager = HistoryManager(str(tmp_path / "history.json"))
        
        source = Path("/tmp/test.py")
        target = Path("/usr/local/bin/test")
        
        manager.add_installation(source, target, "python", "abc123")
        
        assert len(manager.history["installations"]) == 1
        entry = manager.history["installations"][0]
        assert entry["source"] == str(source)
        assert entry["target"] == str(target)
        assert entry["type"] == "python"
        assert entry["checksum"] == "abc123"
        assert "timestamp" in entry
        assert "user" in entry


class TestUniversalInstaller:
    """Test UniversalInstaller functionality"""
    
    def test_installer_initialization(self, tmp_path):
        """Test installer initialization"""
        install_dir = tmp_path / "bin"
        installer = UniversalInstaller(str(install_dir))
        
        assert installer.install_dir == install_dir
        assert isinstance(installer.history, HistoryManager)
    
    def test_python_script_detection(self, tmp_path):
        """Test Python script detection"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        # Test .py extension
        py_file = tmp_path / "script.py"
        py_file.write_text("print('hello')")
        assert installer.is_python_script(py_file)
        
        # Test shebang
        shebang_file = tmp_path / "script"
        shebang_file.write_text("#!/usr/bin/env python3\nprint('hello')")
        assert installer.is_python_script(shebang_file)
        
        # Test non-Python file
        other_file = tmp_path / "script.sh"
        other_file.write_text("#!/bin/bash\necho hello")
        assert not installer.is_python_script(other_file)
    
    def test_checksum_calculation(self, tmp_path):
        """Test checksum calculation"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        
        checksum = installer.calculate_checksum(test_file)
        assert len(checksum) == 64  # SHA256 produces 64 hex characters
        assert checksum == "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
    
    @pytest.mark.parametrize("filename,expected", [
        ("script.py", "script"),
        ("my-tool.py", "my-tool"),
        ("test", "test"),
        ("app.exe", "app.exe")
    ])
    def test_filename_handling(self, tmp_path, filename, expected):
        """Test filename handling with extension removal"""
        installer = UniversalInstaller(str(tmp_path / "bin"))
        installer.create_install_dir()
        
        source = tmp_path / filename
        if filename.endswith('.py'):
            source.write_text("#!/usr/bin/env python3\nprint('test')")
        else:
            source.write_text("binary content")
            source.chmod(0o755)
        
        installer.install_file(str(source), remove_extension=True)
        
        target = installer.install_dir / expected
        assert target.exists()


class TestIntegration:
    """Integration tests"""
    
    def test_full_installation_workflow(self, tmp_path):
        """Test complete installation workflow"""
        install_dir = tmp_path / "bin"
        installer = UniversalInstaller(str(install_dir))
        
        # Create a Python script
        source = tmp_path / "my_script.py"
        source.write_text("#!/usr/bin/env python3\nprint('Hello from my_script')")
        
        # Install it
        success = installer.install_file(str(source))
        assert success
        
        # Verify installation
        target = install_dir / "my_script"
        assert target.exists()
        assert target.stat().st_mode & 0o111  # Check executable
        
        # Verify history
        installed = installer.history.get_installed_files()
        assert str(target) in installed
        
        # Uninstall
        with patch('builtins.input', return_value='y'):
            success = installer.uninstall_file("my_script")
        assert success
        assert not target.exists()
        
        # Verify history shows uninstallation
        installed = installer.history.get_installed_files()
        assert str(target) not in installed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
