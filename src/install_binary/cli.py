"""
Command-line interface for install-binary tool
"""

import sys
import argparse
from pathlib import Path

from .constants import DEFAULT_INSTALL_DIR, USER_INSTALL_DIR
from .installer import UniversalInstaller


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser"""
    parser = argparse.ArgumentParser(
        description="Install compiled binaries and Python scripts with history tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Install a binary
  sudo install-binary ./myprogram
  
  # Install a Python script (removes .py extension by default)
  sudo install-binary ./script.py
  
  # Install with custom name
  sudo install-binary ./build/app --name myapp
  
  # View installation history
  sudo install-binary --history
  install-binary --history --user  # User installations
  
  # Search history
  sudo install-binary --history --search myapp
  
  # Install this installer itself
  sudo install-binary --install-self
  
  # User installation (no sudo needed)
  install-binary ./script.py --user
  
  # Uninstall
  sudo install-binary --uninstall myapp
  
Note: This script requires sudo/root privileges for system-wide installation
      Use --user flag to install to ~/.local/bin/ without sudo
        """
    )
    
    parser.add_argument(
        "file_path",
        nargs='?',
        help="Path to the binary or script to install"
    )
    
    parser.add_argument(
        "--name", "-n",
        dest="target_name",
        help="Custom name for the installed file (default: use source filename)"
    )
    
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force overwrite if target already exists"
    )
    
    parser.add_argument(
        "--keep-extension", "-k",
        action="store_true",
        help="Keep .py extension for Python scripts (default: remove)"
    )
    
    parser.add_argument(
        "--install-dir", "-d",
        default=DEFAULT_INSTALL_DIR,
        help=f"Installation directory (default: {DEFAULT_INSTALL_DIR})"
    )
    
    parser.add_argument(
        "--uninstall", "-u",
        metavar="FILE_NAME",
        help="Uninstall a file from installation directory"
    )
    
    parser.add_argument(
        "--user", "-U",
        action="store_true",
        help="Install to user directory (~/.local/bin) instead of system-wide"
    )
    
    parser.add_argument(
        "--install-self", "-S",
        action="store_true",
        help="Install this installer script itself to system PATH"
    )
    
    parser.add_argument(
        "--history", "-H",
        action="store_true",
        help="Show installation history"
    )
    
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Show all history entries (with --history)"
    )
    
    parser.add_argument(
        "--search", "-s",
        metavar="QUERY",
        help="Search history for specific files (with --history)"
    )
    
    parser.add_argument(
        "--history-file",
        help="Custom history file location"
    )
    
    return parser


def main() -> None:
    """Main entry point for CLI"""
    parser = create_parser()
    args = parser.parse_args()
    
    # Handle user installation mode
    if args.user:
        install_dir = Path.home() / USER_INSTALL_DIR
        print(f"📁 Installing to user directory: {install_dir}")
    else:
        install_dir = args.install_dir
    
    installer = UniversalInstaller(install_dir, args.history_file)
    
    # Handle history display
    if args.history:
        if args.search:
            installer.history.search_history(args.search)
        else:
            installer.history.display_history(show_all=args.all)
        sys.exit(0)
    
    # Check privileges for system-wide installation
    if not args.user and not installer.check_privileges():
        print("✗ Error: This script requires sudo/root privileges for system-wide installation.")
        print("  Run with: sudo install-binary <file_path>")
        print("  Or use --user flag to install to ~/.local/bin/ without sudo")
        sys.exit(1)
    
    # Handle self-installation
    if args.install_self:
        success = installer.install_self(force=args.force)
        if success:
            print("\n" + "=" * 50)
            print("🎉 Self-installation complete!")
            print("You can now use 'install-binary' command from anywhere:")
            print("  install-binary ./myprogram")
            print("  install-binary ./script.py")
            print("  install-binary --history")
        sys.exit(0 if success else 1)
    
    # Handle uninstall mode
    if args.uninstall:
        success = installer.uninstall_file(args.uninstall)
        sys.exit(0 if success else 1)
    
    # Check if file path was provided for installation
    if not args.file_path:
        parser.print_help()
        sys.exit(1)
    
    # Perform installation
    success = installer.install_file(
        args.file_path,
        target_name=args.target_name,
        force=args.force,
        remove_extension=not args.keep_extension
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
