#!/usr/bin/env python3
"""
Additional tests for history module to improve coverage
"""

import pytest
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open, MagicMock

# Add the parent directory to the path to import our module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.installer.history import HistoryManager
from src.installer.exceptions import ValidationError, PermissionError, InstallationError


class TestHistoryDisplay:
    """Test history display functionality"""
    
    def test_display_empty_history(self, tmp_path, capsys):
        """Test displaying empty history"""
        history = HistoryManager(str(tmp_path / "history.json"))
        history.display_history()
        
        captured = capsys.readouterr()
        assert "No files currently tracked as installed" in captured.out
    
    def test_display_history_with_entries(self, tmp_path, capsys):
        """Test displaying history with entries"""
        history = HistoryManager(str(tmp_path / "history.json"))
        
        # Add some installations
        history.add_installation(
            Path("/tmp/source.py"),
            Path("/usr/local/bin/mytool"),
            "python",
            "abc123"
        )
        
        history.display_history()
        
        captured = capsys.readouterr()
        assert "CURRENTLY INSTALLED FILES" in captured.out
        assert "mytool" in captured.out
        assert "python" in captured.out
        assert "Destination" in captured.out
        assert "/usr/local/bin/mytool" in captured.out
    
    def test_display_all_history(self, tmp_path, capsys):
        """Test displaying all history entries"""
        history = HistoryManager(str(tmp_path / "history.json"))
        
        # Add installation and uninstallation
        history.add_installation(
            Path("/tmp/source.py"),
            Path("/usr/local/bin/mytool"),
            "python",
            "abc123"
        )
        history.add_uninstallation(Path("/usr/local/bin/mytool"))
        
        history.display_history(show_all=True)
        
        captured = capsys.readouterr()
        assert "INSTALLATION HISTORY (ALL ACTIONS)" in captured.out
        assert "INSTALL" in captured.out
        assert "UNINSTALL" in captured.out
        assert "Source:" in captured.out
        assert "Destination:" in captured.out
        assert "Checksum:" in captured.out
    
    def test_display_history_with_limit(self, tmp_path, capsys):
        """Test history display with limit"""
        history = HistoryManager(str(tmp_path / "history.json"))
        
        # Add many entries
        for i in range(30):
            history.add_installation(
                Path(f"/tmp/source{i}.py"),
                Path(f"/usr/local/bin/tool{i}"),
                "python"
            )
        
        history.display_history(show_all=True, limit=10)
        
        captured = capsys.readouterr()
        assert "Showing last 10 entries" in captured.out


class TestHistorySearch:
    """Test history search functionality"""
    
    def test_search_no_results(self, tmp_path, capsys):
        """Test search with no results"""
        history = HistoryManager(str(tmp_path / "history.json"))
        history.add_installation(
            Path("/tmp/source.py"),
            Path("/usr/local/bin/mytool"),
            "python"
        )
        
        history.search_history("nonexistent")
        
        captured = capsys.readouterr()
        assert "No history entries found matching 'nonexistent'" in captured.out
    
    def test_search_with_results(self, tmp_path, capsys):
        """Test search with results"""
        history = HistoryManager(str(tmp_path / "history.json"))
        
        # Add various entries
        history.add_installation(
            Path("/tmp/myapp.py"),
            Path("/usr/local/bin/myapp"),
            "python"
        )
        history.add_installation(
            Path("/tmp/other.py"),
            Path("/usr/local/bin/other"),
            "python"
        )
        history.add_uninstallation(Path("/usr/local/bin/myapp"))
        
        history.search_history("myapp")
        
        captured = capsys.readouterr()
        assert "SEARCH RESULTS FOR: myapp" in captured.out
        assert "myapp" in captured.out
        assert "INSTALL" in captured.out
        assert "UNINSTALL" in captured.out
        # Should not include 'other'
        assert captured.out.count("other") == 0


class TestHistoryErrorCases:
    """Test error handling in history module"""
    
    def test_load_corrupted_json(self, tmp_path):
        """Test loading corrupted JSON file"""
        history_file = tmp_path / "history.json"
        history_file.write_text("{invalid json")
        
        with pytest.raises(ValidationError, match="Invalid JSON"):
            HistoryManager(str(history_file))
    
    def test_load_invalid_structure(self, tmp_path):
        """Test loading JSON with invalid structure"""
        history_file = tmp_path / "history.json"
        history_file.write_text('{"wrong": "structure"}')
        
        with pytest.raises(ValidationError, match="missing required keys"):
            HistoryManager(str(history_file))
    
    def test_save_permission_denied(self, tmp_path):
        """Test saving when permission denied"""
        history = HistoryManager(str(tmp_path / "history.json"))
        
        # Mock the temp file creation to raise permission error
        with patch('tempfile.mkstemp', side_effect=OSError(13, "Permission denied")):
            with pytest.raises(PermissionError, match="Permission denied"):
                history.save_history()
    
    def test_save_disk_full(self, tmp_path):
        """Test saving when disk is full"""
        history = HistoryManager(str(tmp_path / "history.json"))
        
        # Mock the temp file creation to raise disk full error
        with patch('tempfile.mkstemp', side_effect=OSError(28, "No space left on device")):
            with pytest.raises(InstallationError, match="No space left on device"):
                history.save_history()


class TestHistoryFileOperations:
    """Test file operation edge cases"""
    
    def test_history_file_permissions(self, tmp_path):
        """Test that history file gets correct permissions"""
        history = HistoryManager(str(tmp_path / "history.json"))
        history.save_history()
        
        # Check file was created with correct permissions
        assert history.history_file.exists()
        stat_info = history.history_file.stat()
        assert oct(stat_info.st_mode)[-3:] == '644'
    
    def test_get_installed_files_with_duplicates(self, tmp_path):
        """Test get_installed_files handles duplicates correctly"""
        history = HistoryManager(str(tmp_path / "history.json"))
        
        # Install same file multiple times
        target = Path("/usr/local/bin/mytool")
        history.add_installation(Path("/tmp/v1.py"), target, "python")
        history.add_installation(Path("/tmp/v2.py"), target, "python")
        
        installed = history.get_installed_files()
        assert len(installed) == 1
        assert str(target) in installed
        # Should have the latest installation
        assert installed[str(target)]["source"] == "/tmp/v2.py"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
