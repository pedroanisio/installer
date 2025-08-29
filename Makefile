# Makefile for install-binary
# Handles man page installation and other build tasks

PREFIX ?= /usr/local
BINDIR = $(PREFIX)/bin
MANDIR = $(PREFIX)/share/man/man1
PYTHON ?= python3

.PHONY: all install install-man install-bin uninstall clean test help

all: help

help:
	@echo "install-binary Makefile"
	@echo "======================"
	@echo ""
	@echo "Available targets:"
	@echo "  make install       - Install the tool and man page"
	@echo "  make install-bin   - Install only the binary"
	@echo "  make install-man   - Install only the man page"
	@echo "  make uninstall     - Remove the tool and man page"
	@echo "  make test          - Run the test suite"
	@echo "  make clean         - Clean build artifacts"
	@echo "  make help          - Show this help message"
	@echo ""
	@echo "Variables:"
	@echo "  PREFIX=$(PREFIX)"
	@echo "  PYTHON=$(PYTHON)"

install: install-bin install-man
	@echo "Installation complete!"

install-bin:
	@echo "Installing install-binary to $(BINDIR)..."
	@mkdir -p $(BINDIR)
	@$(PYTHON) -m install_binary --install-self --force
	@echo "Binary installed successfully!"

install-man:
	@echo "Installing man page to $(MANDIR)..."
	@mkdir -p $(MANDIR)
	@cp docs/install-binary.1 $(MANDIR)/install-binary.1
	@chmod 644 $(MANDIR)/install-binary.1
	@echo "Man page installed successfully!"
	@echo "You can now use: man install-binary"

uninstall:
	@echo "Uninstalling install-binary..."
	@rm -f $(BINDIR)/install-binary
	@rm -f $(MANDIR)/install-binary.1
	@echo "Uninstallation complete!"

test:
	@echo "Running test suite..."
	@$(PYTHON) -m pytest tests/ -v

clean:
	@echo "Cleaning build artifacts..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/
	@echo "Clean complete!"

# Development targets
.PHONY: dev-install coverage lint format

dev-install:
	@echo "Installing in development mode..."
	@$(PYTHON) -m pip install -e ".[dev]"

coverage:
	@echo "Running tests with coverage..."
	@$(PYTHON) -m pytest tests/ --cov=src/install_binary --cov-report=term-missing --cov-report=html

lint:
	@echo "Running linters..."
	@$(PYTHON) -m flake8 src tests
	@$(PYTHON) -m mypy src

format:
	@echo "Formatting code..."
	@$(PYTHON) -m black src tests
	@$(PYTHON) -m isort src tests
