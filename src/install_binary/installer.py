"""
Main installer functionality for install-binary tool
"""

import os
import stat
import shutil
import hashlib
import tempfile
from pathlib import Path
from typing import Optional, Union, Any

from .constants import (
    DEFAULT_INSTALL_DIR,
    DEFAULT_PERMISSIONS,
    CHUNK_SIZE,
)
from .exceptions import ValidationError, PermissionError, InstallationError
from .history import HistoryManager


class UniversalInstaller:
    """Universal installer for binaries and scripts with security features"""
    
    def __init__(self, install_dir: str = DEFAULT_INSTALL_DIR, 
                 history_file: Optional[str] = None) -> None:
        self.install_dir = Path(install_dir)
        self.history = HistoryManager(history_file)
        
    def check_privileges(self) -> bool:
        """Check if script is run with sudo/root privileges"""
        return os.geteuid() == 0
    
    def validate_target_path(self, target_path: Path) -> None:
        """Validate that target path is within allowed directory"""
        try:
            # Resolve to absolute paths
            target_resolved = target_path.resolve()
            allowed_dir_resolved = self.install_dir.resolve()
            
            # Check if target is within allowed directory
            if target_resolved.parent != allowed_dir_resolved:
                raise ValidationError(
                    f"Target path {target_path} is outside allowed directory {self.install_dir}"
                )
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Invalid target path: {e}")
    
    def is_symlink_or_hardlink(self, file_path: Path) -> bool:
        """Check if file is a symlink or hardlink"""
        try:
            # Check for symlink
            if file_path.is_symlink():
                return True
            
            # Check for hardlink (link count > 1)
            stat_info = file_path.stat()
            if stat_info.st_nlink > 1:
                return True
                
            return False
        except OSError:
            return False
    
    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file"""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(CHUNK_SIZE), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except OSError as e:
            raise ValidationError(f"Cannot calculate checksum: {e}")
    
    def is_python_script(self, file_path: Path) -> bool:
        """Check if file is a Python script"""
        file_path = Path(file_path)
        
        # Check by extension
        if file_path.suffix.lower() in ['.py', '.pyw']:
            return True
        
        # Check by shebang
        try:
            with open(file_path, 'rb') as f:
                first_bytes = f.read(100)
                if first_bytes.startswith(b'#!'):
                    first_line = first_bytes.split(b'\n')[0].decode('utf-8', errors='ignore')
                    if 'python' in first_line.lower():
                        return True
        except OSError:
            # If we can't read the file, it's not a Python script
            return False
        
        return False
    
    def ensure_shebang(self, script_path: Path) -> str:
        """Ensure Python script has proper shebang"""
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if shebang exists
        if not content.startswith('#!'):
            print(f"Adding shebang to {script_path.name}")
            # Add shebang
            shebang = '#!/usr/bin/env python3\n'
            return shebang + content
        else:
            # Verify it's a Python shebang
            first_line = content.split('\n')[0]
            if 'python' not in first_line.lower():
                print(f"Warning: Script has non-Python shebang: {first_line}")
            return content
    
    def validate_source(self, source_path: Union[str, Path]) -> Path:
        """Validate the source file with security checks"""
        source = Path(source_path)
        
        # Check existence first (before resolving)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        # Security check: prevent symlinks (check before resolving)
        if self.is_symlink_or_hardlink(source):
            raise ValidationError(
                f"Source file {source_path} is a symlink or hardlink. "
                "For security reasons, symlinks are not allowed."
            )
        
        # Now resolve to absolute path
        source = source.resolve()
        
        if not source.is_file():
            raise ValidationError(f"Source is not a file: {source_path}")
        
        # Store initial stat for TOCTOU prevention
        self._source_stat = source.stat()
        
        # Check file type
        if self.is_python_script(source):
            print(f"✓ Detected Python script: {source.name}")
        else:
            # Check if binary is executable
            if not os.access(source, os.X_OK):
                print(f"⚠ Warning: {source_path} is not currently executable")
            print(f"✓ Detected binary/script: {source.name}")
        
        return source
    
    def verify_source_unchanged(self, source_path: Path) -> None:
        """Verify source file hasn't changed since validation (TOCTOU prevention)"""
        try:
            current_stat = source_path.stat()
            if (current_stat.st_mtime != self._source_stat.st_mtime or
                current_stat.st_size != self._source_stat.st_size):
                raise ValidationError(
                    "File was modified during operation. Installation aborted for security."
                )
        except AttributeError:
            raise ValidationError("Source file was not properly validated")
        except OSError as e:
            raise ValidationError(f"Cannot verify source file: {e}")
    
    def create_install_dir(self) -> None:
        """Ensure the installation directory exists with proper permissions"""
        try:
            if not self.install_dir.exists():
                print(f"Creating directory: {self.install_dir}")
                self.install_dir.mkdir(parents=True, exist_ok=True)
            
            # Verify we can write to the directory
            if not os.access(self.install_dir, os.W_OK):
                raise PermissionError(
                    f"No write permission for directory: {self.install_dir}"
                )
        except OSError as e:
            if e.errno == 13:  # EACCES
                raise PermissionError(f"Permission denied creating directory: {e}")
            elif e.errno == 28:  # ENOSPC
                raise InstallationError("No space left on device")
            else:
                raise InstallationError(f"Failed to create directory: {e}")
    
    def install_file(self, source_path: Union[str, Path], target_name: Optional[str] = None, 
                     force: bool = False, remove_extension: bool = True) -> bool:
        """Install binary or script to target directory with security checks"""
        try:
            # Validate source
            source = self.validate_source(source_path)
            is_python = self.is_python_script(source)
            
            # Calculate checksum before any operations
            checksum = self.calculate_checksum(source)
            print(f"📊 Source checksum: {checksum[:16]}...")
            
            # Determine target name
            if target_name:
                target_filename = target_name
            else:
                target_filename = source.name
                # Optionally remove .py extension for Python scripts
                if is_python and remove_extension and target_filename.endswith('.py'):
                    target_filename = target_filename[:-3]
                    print(f"Removing .py extension: installing as '{target_filename}'")
            
            # Validate target filename (prevent directory traversal)
            if '/' in target_filename or '\\' in target_filename or '..' in target_filename:
                raise ValidationError("Invalid target filename: contains path separators")
            
            target = self.install_dir / target_filename
            
            # Validate target path
            self.validate_target_path(target)
            
            # Check if target already exists
            if target.exists() and not force:
                response = input(f"File {target} already exists. Overwrite? [y/N]: ")
                if response.lower() != 'y':
                    print("Installation cancelled.")
                    return False
            
            # Create install directory if needed
            self.create_install_dir()
            
            # Verify source hasn't changed (TOCTOU check)
            self.verify_source_unchanged(source)
            
            # Use atomic operations with temporary file
            temp_target = target.with_suffix('.tmp.' + str(os.getpid()))
            
            try:
                # Handle Python scripts specially
                if is_python:
                    print(f"Processing Python script: {source}")
                    
                    # Read and ensure shebang
                    content = self.ensure_shebang(source)
                    
                    # Write to temporary target
                    print(f"Writing {target}")
                    with open(temp_target, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    # Copy file stats (preserving timestamps)
                    shutil.copystat(source, temp_target)
                else:
                    # Copy binary or non-Python script
                    print(f"Copying {source} to {target}")
                    shutil.copy2(source, temp_target)
                
                # Set permissions to 755 (rwxr-xr-x)
                print(f"Setting permissions to {oct(DEFAULT_PERMISSIONS)} for {target}")
                temp_target.chmod(DEFAULT_PERMISSIONS)
                
                # Final TOCTOU check before atomic move
                self.verify_source_unchanged(source)
                
                # Atomic move to final location
                os.replace(temp_target, target)
                
                # Verify installation
                if self.verify_installation(target):
                    # Record in history
                    file_type = "python" if is_python else "binary"
                    self.history.add_installation(source, target, file_type, checksum)
                    
                    print(f"✓ Successfully installed {target_filename} to {self.install_dir}")
                    print(f"✓ {'Script' if is_python else 'Binary'} is now available system-wide as '{target_filename}'")
                    print(f"📝 Installation recorded in history")
                    
                    # Test command availability
                    print(f"✓ You can now run it with: {target_filename}")
                    return True
                else:
                    # Clean up on verification failure
                    try:
                        target.unlink()
                    except OSError:
                        pass
                    raise InstallationError("Installation verification failed")
                    
            except Exception:
                # Clean up temporary file on error
                try:
                    temp_target.unlink()
                except OSError:
                    pass
                raise
                
        except (ValidationError, PermissionError, InstallationError) as e:
            print(f"✗ Installation failed: {e}")
            return False
        except OSError as e:
            if e.errno == 28:  # ENOSPC
                print(f"✗ Installation failed: No space left on device")
            else:
                print(f"✗ Installation failed: {e}")
            return False
        except Exception as e:
            print(f"✗ Unexpected error during installation: {e}")
            return False
    
    def verify_installation(self, target_path: Path) -> bool:
        """Verify the installed file with strict checks"""
        target = Path(target_path)
        
        if not target.exists():
            raise ValidationError(f"Verification failed: {target} does not exist")
        
        # Check permissions
        try:
            st = target.stat()
            mode = st.st_mode
            
            # Check if it's executable by owner, readable by all, executable by all
            expected_perms = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | \
                            stat.S_IRGRP | stat.S_IXGRP | \
                            stat.S_IROTH | stat.S_IXOTH
            
            if (mode & expected_perms) != expected_perms:
                raise ValidationError(
                    f"Permission verification failed. Expected: {oct(DEFAULT_PERMISSIONS)}, "
                    f"Got: {oct(mode)[-3:]}"
                )
            
            print(f"✓ Permissions verified: {oct(mode)[-3:]}")
            
            # Verify it's not a symlink (additional security check)
            if target.is_symlink():
                raise ValidationError("Target became a symlink during installation")
            
            return True
            
        except OSError as e:
            raise ValidationError(f"Cannot verify installation: {e}")
    
    def uninstall_file(self, file_name: str) -> bool:
        """Remove a file from installation directory with validation"""
        # Validate filename
        if '/' in file_name or '\\' in file_name or '..' in file_name:
            print(f"✗ Invalid filename: {file_name}")
            return False
            
        target = self.install_dir / file_name
        
        # Validate target path
        try:
            self.validate_target_path(target)
        except ValidationError as e:
            print(f"✗ Invalid target: {e}")
            return False
        
        if not target.exists():
            print(f"File not found: {target}")
            # Check history to see if it was previously installed
            installed = self.history.get_installed_files()
            for path in installed:
                if Path(path).name == file_name:
                    print(f"ℹ️  File was previously installed at: {path}")
                    break
            return False
        
        try:
            response = input(f"Remove {target}? [y/N]: ")
            if response.lower() == 'y':
                target.unlink()
                # Record in history
                self.history.add_uninstallation(target)
                print(f"✓ Removed {target}")
                print(f"📝 Uninstallation recorded in history")
                return True
            else:
                print("Removal cancelled.")
                return False
        except OSError as e:
            print(f"✗ Removal failed: {e}")
            return False
    
    def install_self(self, force: bool = False) -> bool:
        """Install this script itself to system PATH"""
        print("🔧 Self-installation mode")
        print("=" * 50)
        
        try:
            # Get the path of this script
            script_path = Path(__file__).resolve()
            print(f"Installing myself from: {script_path}")
            
            # Verify this file exists and is readable
            if not script_path.exists() or not script_path.is_file():
                raise ValidationError("Cannot find script file for self-installation")
            
            # Install with name 'install-binary' (without .py extension)
            return self.install_file(
                script_path, 
                target_name="install-binary",
                force=force,
                remove_extension=True
            )
        except Exception as e:
            print(f"✗ Self-installation failed: {e}")
            return False
