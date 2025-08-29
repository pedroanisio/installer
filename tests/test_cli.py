#!/usr/bin/env python3
"""
Test suite for CLI functionality
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add the parent directory to the path to import our module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.install_binary.cli import create_parser, main
from src.install_binary import ValidationError


class TestCLIParser:
    """Test argument parser creation and configuration"""
    
    def test_create_parser(self):
        """Test that parser is created with all expected arguments"""
        parser = create_parser()
        
        # Test that parser exists
        assert parser is not None
        
        # Get all actions (arguments)
        actions = {action.dest for action in parser._actions if action.dest != 'help'}
        
        expected_args = {
            'file_path', 'target_name', 'force', 'keep_extension',
            'install_dir', 'uninstall', 'user', 'install_self',
            'history', 'all', 'search', 'history_file'
        }
        
        assert expected_args.issubset(actions)
    
    def test_parser_defaults(self):
        """Test default values for arguments"""
        parser = create_parser()
        args = parser.parse_args([])
        
        assert args.file_path is None
        assert args.force is False
        assert args.keep_extension is False
        assert args.user is False
        assert args.install_self is False
        assert args.history is False
        assert args.all is False
        assert args.install_dir == "/usr/local/bin"


class TestCLIMain:
    """Test main CLI functionality"""
    
    @patch('src.install_binary.cli.UniversalInstaller')
    def test_history_mode(self, mock_installer_class):
        """Test history display mode"""
        mock_installer = MagicMock()
        mock_installer_class.return_value = mock_installer
        
        with patch('sys.argv', ['install-binary', '--history']):
            with pytest.raises(SystemExit) as exc_info:
                main()
        
        assert exc_info.value.code == 0
        mock_installer.history.display_history.assert_called_once_with(show_all=False)
    
    @patch('src.install_binary.cli.UniversalInstaller')
    def test_history_search_mode(self, mock_installer_class):
        """Test history search mode"""
        mock_installer = MagicMock()
        mock_installer_class.return_value = mock_installer
        
        with patch('sys.argv', ['install-binary', '--history', '--search', 'myapp']):
            with pytest.raises(SystemExit) as exc_info:
                main()
        
        assert exc_info.value.code == 0
        mock_installer.history.search_history.assert_called_once_with('myapp')
    
    @patch('src.install_binary.cli.UniversalInstaller')
    def test_user_mode(self, mock_installer_class):
        """Test user installation mode"""
        mock_installer = MagicMock()
        mock_installer_class.return_value = mock_installer
        
        with patch('sys.argv', ['install-binary', '--user', '--history']):
            with pytest.raises(SystemExit) as exc_info:
                main()
        
        assert exc_info.value.code == 0
        # Should use user directory
        assert mock_installer_class.call_args[0][0] == Path.home() / ".local/bin"
    
    @patch('src.install_binary.cli.UniversalInstaller')
    @patch('builtins.print')
    def test_privilege_check_failure(self, mock_print, mock_installer_class):
        """Test privilege check when not running as root"""
        mock_installer = MagicMock()
        mock_installer.check_privileges.return_value = False
        mock_installer_class.return_value = mock_installer
        
        with patch('sys.argv', ['install-binary', 'myfile']):
            with pytest.raises(SystemExit) as exc_info:
                main()
        
        assert exc_info.value.code == 1
        # Should print error message
        assert any("sudo/root privileges" in str(call) for call in mock_print.call_args_list)
    
    @patch('src.install_binary.cli.UniversalInstaller')
    def test_install_self_mode(self, mock_installer_class):
        """Test self-installation mode"""
        mock_installer = MagicMock()
        mock_installer.install_self.return_value = True
        mock_installer_class.return_value = mock_installer
        
        with patch('sys.argv', ['install-binary', '--install-self']):
            with pytest.raises(SystemExit) as exc_info:
                main()
        
        assert exc_info.value.code == 0
        mock_installer.install_self.assert_called_once()
    
    @patch('src.install_binary.cli.UniversalInstaller')
    def test_uninstall_mode(self, mock_installer_class):
        """Test uninstallation mode"""
        mock_installer = MagicMock()
        mock_installer.uninstall_file.return_value = True
        mock_installer.check_privileges.return_value = True
        mock_installer_class.return_value = mock_installer
        
        with patch('sys.argv', ['install-binary', '--uninstall', 'myapp']):
            with pytest.raises(SystemExit) as exc_info:
                main()
        
        assert exc_info.value.code == 0
        mock_installer.uninstall_file.assert_called_once_with('myapp')
    
    @patch('src.install_binary.cli.UniversalInstaller')
    def test_install_file_mode(self, mock_installer_class):
        """Test normal file installation mode"""
        mock_installer = MagicMock()
        mock_installer.install_file.return_value = True
        mock_installer.check_privileges.return_value = True
        mock_installer_class.return_value = mock_installer
        
        with patch('sys.argv', ['install-binary', 'myfile.py', '--name', 'custom']):
            with pytest.raises(SystemExit) as exc_info:
                main()
        
        assert exc_info.value.code == 0
        mock_installer.install_file.assert_called_once_with(
            'myfile.py',
            target_name='custom',
            force=False,
            remove_extension=True
        )
    
    @patch('src.install_binary.cli.UniversalInstaller')
    def test_no_file_provided(self, mock_installer_class):
        """Test behavior when no file is provided"""
        mock_installer = MagicMock()
        mock_installer.check_privileges.return_value = True
        mock_installer_class.return_value = mock_installer
        
        with patch('sys.argv', ['install-binary']):
            with patch('src.install_binary.cli.create_parser') as mock_parser_func:
                mock_parser = MagicMock()
                mock_parser_func.return_value = mock_parser
                mock_parser.parse_args.return_value = MagicMock(
                    file_path=None, history=False, install_self=False,
                    uninstall=None, user=False, history_file=None,
                    install_dir='/usr/local/bin'
                )
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 1
                mock_parser.print_help.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
