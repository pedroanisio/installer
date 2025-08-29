"""
History management for installation tracking
"""

import os
import json
import fcntl
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

from .constants import (
    HISTORY_DIR_SYSTEM,
    HISTORY_DIR_USER,
    HISTORY_FILE_NAME,
)
from .exceptions import ValidationError, PermissionError, InstallationError


class HistoryManager:
    """Manage installation/uninstallation history with thread-safe operations"""
    
    def __init__(self, history_file: Optional[str] = None) -> None:
        if history_file:
            self.history_file = Path(history_file)
        else:
            # Use system-wide location if root, user location otherwise
            if os.geteuid() == 0:
                self.history_file = Path(HISTORY_DIR_SYSTEM) / HISTORY_FILE_NAME
            else:
                config_dir = Path.home() / HISTORY_DIR_USER
                config_dir.mkdir(parents=True, exist_ok=True)
                self.history_file = config_dir / "history.json"
        
        self.history = self.load_history()
    
    def load_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load history from file with proper error handling"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    # Validate structure
                    if not isinstance(data, dict):
                        raise ValidationError("History file must contain a JSON object")
                    if "installations" not in data or "uninstallations" not in data:
                        raise ValidationError("History file missing required keys")
                    return data
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON in history file: {e}")
            except OSError as e:
                raise PermissionError(f"Cannot read history file: {e}")
        return {"installations": [], "uninstallations": []}
    
    def save_history(self) -> None:
        """Save history to file with file locking to prevent race conditions"""
        try:
            # Ensure directory exists
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Use atomic write with temporary file
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.history_file.parent,
                prefix=".history_",
                suffix=".tmp"
            )
            
            try:
                with os.fdopen(temp_fd, 'w') as f:
                    # Acquire exclusive lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    try:
                        json.dump(self.history, f, indent=2, default=str)
                        f.flush()
                        os.fsync(f.fileno())
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                
                # Set appropriate permissions before moving
                os.chmod(temp_path, 0o644)
                
                # Atomic move
                os.replace(temp_path, self.history_file)
                
            except Exception:
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                raise
                
        except OSError as e:
            if e.errno == 28:  # ENOSPC
                raise InstallationError("No space left on device")
            elif e.errno == 13:  # EACCES
                raise PermissionError(f"Permission denied writing history: {e}")
            else:
                raise InstallationError(f"Failed to save history: {e}")
    
    def add_installation(self, source_path: Path, target_path: Path, 
                        file_type: str, checksum: Optional[str] = None) -> None:
        """Record an installation"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "install",
            "source": str(source_path),
            "target": str(target_path),
            "type": file_type,
            "checksum": checksum,
            "user": os.environ.get('SUDO_USER', os.environ.get('USER', 'unknown')),
            "uid": os.getuid(),
        }
        self.history["installations"].append(entry)
        self.save_history()
    
    def add_uninstallation(self, target_path: Path) -> None:
        """Record an uninstallation"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "uninstall",
            "target": str(target_path),
            "user": os.environ.get('SUDO_USER', os.environ.get('USER', 'unknown')),
            "uid": os.getuid(),
        }
        self.history["uninstallations"].append(entry)
        self.save_history()
    
    def get_installed_files(self) -> Dict[str, Dict[str, Any]]:
        """Get list of currently installed files based on history"""
        installed = {}
        
        # Track all installations
        for entry in self.history["installations"]:
            target = entry["target"]
            installed[target] = entry
        
        # Remove uninstalled files
        for entry in self.history["uninstallations"]:
            target = entry["target"]
            installed.pop(target, None)
        
        return installed
    
    def display_history(self, show_all: bool = False, limit: int = 20) -> None:
        """Display installation history"""
        if show_all:
            # Combine and sort all entries
            all_entries = []
            for entry in self.history["installations"]:
                all_entries.append(entry)
            for entry in self.history["uninstallations"]:
                all_entries.append(entry)
            
            # Sort by timestamp
            all_entries.sort(key=lambda x: x["timestamp"], reverse=True)
            
            if not all_entries:
                print("No history found.")
                return
            
            print(f"\n{'='*80}")
            print(f"{'INSTALLATION HISTORY (ALL ACTIONS)':^80}")
            print(f"{'='*80}\n")
            
            for entry in all_entries[:limit] if limit else all_entries:
                self._print_entry(entry)
            
            if limit and len(all_entries) > limit:
                print(f"\n(Showing last {limit} entries. Use --all to see everything)")
        
        else:
            # Show currently installed files
            installed = self.get_installed_files()
            
            if not installed:
                print("No files currently tracked as installed.")
                return
            
            print(f"\n{'='*80}")
            print(f"{'CURRENTLY INSTALLED FILES':^80}")
            print(f"{'='*80}\n")
            
            # Sort by installation date
            sorted_installed = sorted(installed.items(), 
                                    key=lambda x: x[1].get("timestamp", ""), 
                                    reverse=True)
            
            # Print header
            print(f"{'Status':6} {'Name':25} {'Type':8} {'Installed':16} {'User':10} {'Destination'}")
            print("-" * 80)
            
            for target, entry in sorted_installed:
                target_path = Path(target)
                exists = "✓" if target_path.exists() else "✗"
                
                timestamp = entry.get("timestamp", "unknown")
                if timestamp != "unknown":
                    dt = datetime.fromisoformat(timestamp)
                    timestamp = dt.strftime("%Y-%m-%d %H:%M")
                
                print(f"{exists:6} {target_path.name:25} {entry.get('type', 'unknown'):8} "
                      f"{timestamp:16} {entry.get('user', 'unknown'):10} {target}")
            
            print(f"\n{'='*80}")
            print(f"Legend: ✓ = exists, ✗ = missing")
            print(f"Total: {len(installed)} files tracked")
    
    def _print_entry(self, entry: Dict[str, Any]) -> None:
        """Print a single history entry"""
        timestamp = entry.get("timestamp", "unknown")
        if timestamp != "unknown":
            dt = datetime.fromisoformat(timestamp)
            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
        
        action = entry.get("action", "unknown")
        symbol = "📦" if action == "install" else "🗑️"
        
        target = Path(entry.get("target", "unknown"))
        user = entry.get("user", "unknown")
        
        print(f"{symbol} [{timestamp}] {action.upper():10} {target.name:25} by {user}")
        
        if action == "install":
            if "source" in entry:
                print(f"   Source: {entry['source']}")
            print(f"   Destination: {entry.get('target', 'unknown')}")
            print(f"   Type: {entry.get('type', 'unknown')}")
            if "checksum" in entry and entry["checksum"]:
                print(f"   Checksum: {entry['checksum'][:16]}...")
    
    def search_history(self, query: str) -> None:
        """Search history for specific files or patterns"""
        results = []
        query_lower = query.lower()
        
        for entry in self.history["installations"]:
            if (query_lower in entry.get("target", "").lower() or 
                query_lower in entry.get("source", "").lower()):
                results.append(entry)
        
        for entry in self.history["uninstallations"]:
            if query_lower in entry.get("target", "").lower():
                results.append(entry)
        
        if not results:
            print(f"No history entries found matching '{query}'")
            return
        
        print(f"\n{'='*80}")
        print(f"SEARCH RESULTS FOR: {query}")
        print(f"{'='*80}\n")
        
        results.sort(key=lambda x: x["timestamp"], reverse=True)
        for entry in results:
            self._print_entry(entry)
