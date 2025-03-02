![Code Quality Checks](https://github.com/safurrier/python-collab-template/workflows/Code%20Quality%20Checks/badge.svg) [![codecov](https://codecov.io/gh/safurrier/python-collab-template/branch/master/graph/badge.svg)](https://codecov.io/gh/safurrier/python-collab-template)

# Python Project Template

A modern Python project template with best practices for development and collaboration.

## Features
- 🚀 Fast dependency management with [uv](https://github.com/astral-sh/uv)
- ✨ Code formatting with [ruff](https://github.com/astral-sh/ruff)
- 🔍 Type checking with [mypy](https://github.com/python/mypy)
- 🧪 Testing with [pytest](https://github.com/pytest-dev/pytest)
- 🐳 Docker support for development and deployment
- 👷 CI/CD with GitHub Actions

## Python Version
This template requires Python 3.9 or higher and defaults to Python 3.12. To use a different version:

```bash
# List available Python versions
uv python list

# Use a specific version (e.g., 3.11)
make setup PYTHON_VERSION=3.11  # or UV_PYTHON_VERSION=3.11 make setup

# View installed Python versions
uv python list --installed
```

uv will automatically download and manage Python versions as needed.

## Quickstart
```bash
# Clone this repo and change directory
git clone git@github.com:safurrier/python-collab-template.git my-project-name
cd my-project-name

# Initialize a new project
make init

# Follow the prompts to configure your project
```

This will:
- Configure project metadata (name, description, author)
- Handle example code (keep, simplify, or remove)
- Initialize a fresh git repository
- Set up development environment
- Configure pre-commit hooks (optional, enabled by default)

Pre-commit hooks will automatically run these checks before each commit:
- Type checking (mypy)
- Linting (ruff)
- Formatting (ruff)
- Tests (pytest)

Alternatively, you can set up manually:
```bash
# Install dependencies and set up the environment
make setup

# Run the suite of tests and checks
make check

# Optional: Remove example code to start fresh
make clean-example
```

## Development Commands

### Quality Checks
```bash
make check      # Run all checks (test, mypy, lint, format)
make test       # Run tests with coverage
make mypy       # Run type checking
make lint       # Run linter
make format     # Run code formatter
```

### Example Code
The repository includes a simple example showing:
- Type hints
- Dataclasses
- Unit tests
- Modern Python practices

To remove the example code and start fresh:
```bash
make clean-example
```
## Docker Support

### Development Environment
```bash
make dev-env    # Start a development container
```

This creates a container with:
- All dependencies installed
- Source code mounted (changes reflect immediately)
- Development tools ready to use

### Production Image
```bash
make build-image    # Build production image
make push-image     # Push to container registry
```

## Project Structure
```
.
├── src/                # Source code
├── tests/             # Test files
├── docker/            # Docker configuration
├── .github/           # GitHub Actions workflows
├── pyproject.toml     # Project configuration
└── Makefile          # Development commands
```

## Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run `make check` to ensure all tests pass
5. Submit a pull request

## License
This project is licensed under the MIT License - see the LICENSE file for details.
