# install-binary

A secure, feature-rich tool for installing binaries and scripts system-wide with comprehensive history tracking.

## Features

- 🔒 **Security-first design**: Protection against symlinks, path traversal, and TOCTOU attacks
- 📝 **History tracking**: Complete audit trail of all installations and uninstallations
- 🐍 **Smart Python handling**: Automatic shebang management and extension removal
- ⚡ **Atomic operations**: Safe installation with rollback on failure
- 🔄 **Thread-safe**: Concurrent operations handled properly
- 🎯 **User & system installs**: Support for both local and system-wide installations
- 🔍 **Search capabilities**: Find previously installed files quickly

## Installation

### Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is an extremely fast Python package manager written in Rust. It's 10-100x faster than pip and pip-tools.

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install with uv
git clone https://github.com/pedroanisio/install-binary.git
cd install-binary
uv pip install -e .

# Or install directly from PyPI (when published)
uv pip install install-binary
```

### Using pip

```bash
# From source
git clone https://github.com/pedroanisio/install-binary.git
cd install-binary
pip install -e .

# From PyPI
pip install install-binary
```

### Self-Installation

The tool can install itself:

```bash
sudo python3 -m install_binary --install-self
```

### Installing with Make (includes man page)

```bash
# Install both binary and man page
sudo make install

# Install only the man page
sudo make install-man

# View the man page after installation
man install-binary
```

## Usage

### Basic Installation

Install a binary or script system-wide:

```bash
sudo install-binary ./myprogram
```

Install a Python script (removes .py extension automatically):

```bash
sudo install-binary ./myscript.py
```

### User Installation

Install to `~/.local/bin` without sudo:

```bash
install-binary ./myprogram --user
```

### Custom Names

Install with a different name:

```bash
sudo install-binary ./build/app-v2.1 --name myapp
```

### View History

See all currently installed files:

```bash
sudo install-binary --history
```

View all installation/uninstallation events:

```bash
sudo install-binary --history --all
```

Search history:

```bash
sudo install-binary --history --search myapp
```

### Uninstallation

Remove an installed file:

```bash
sudo install-binary --uninstall myapp
```

## Security Features

### Path Traversal Protection
The tool validates all paths to ensure files are only installed within the designated directory.

### Symlink Detection
Symlinks and hardlinks are detected and rejected to prevent security vulnerabilities.

### TOCTOU Prevention
Time-of-check to time-of-use attacks are prevented by verifying file integrity throughout the installation process.

### Atomic Operations
All installations use temporary files and atomic moves to ensure system consistency.

## Development

### Setup Development Environment

#### Using uv (Faster)

```bash
# Clone the repository
git clone https://github.com/pedroanisio/install-binary.git
cd install-binary

# Create virtual environment with uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with dependencies
uv pip install -e ".[dev]"
```

#### Using pip

```bash
# Clone the repository
git clone https://github.com/pedroanisio/install-binary.git
cd install-binary

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=install_binary --cov-report=term-missing

# Run specific test file
pytest tests/test_installer.py
```

### Code Quality

```bash
# Format code
black src tests

# Sort imports
isort src tests

# Type checking
mypy src

# Linting
flake8 src tests
```

### Dependency Management with uv

```bash
# Install dependencies faster with uv
uv pip install -r requirements-dev.txt

# Compile dependencies
uv pip compile pyproject.toml -o requirements.txt
uv pip compile pyproject.toml --extra dev -o requirements-dev.txt

# Sync environment with requirements
uv pip sync requirements-dev.txt
```

## Project Structure

```
install-binary/
├── src/
│   └── install_binary/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── constants.py
│       ├── exceptions.py
│       ├── history.py
│       └── installer.py
├── tests/
│   ├── __init__.py
│   ├── test_installer.py
│   ├── test_cli.py
│   ├── test_history.py
│   └── test_installer_additional.py
├── docs/
│   └── install-binary.1      # Man page
├── pyproject.toml
├── setup.py
├── Makefile                  # Build and install tasks
├── README.md
├── LICENSE
└── .gitignore
```

## Requirements

- Python 3.7 or higher
- POSIX-compliant operating system (Linux, macOS)
- `sudo` privileges for system-wide installation

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Add tests for new features
- Update documentation as needed
- Ensure all tests pass before submitting PR
- Maintain test coverage above 85%

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with security best practices in mind
- Inspired by the need for better binary management tools
- Thanks to all contributors

## Support

For bugs and feature requests, please use the [issue tracker](https://github.com/yourusername/install-binary/issues).

## Changelog

### v1.0.0 (2024-01-XX)
- Initial release with full feature set
- Security hardening
- Comprehensive test suite
- Thread-safe operations
