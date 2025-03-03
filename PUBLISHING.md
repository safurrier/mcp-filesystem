# Publishing Guide

This document contains instructions for publishing the package to PyPI.

## Prerequisites

1. Create accounts on [PyPI](https://pypi.org/) and [TestPyPI](https://test.pypi.org/) (optional for testing)
2. Install build tools:
   ```bash
   uv pip install --upgrade build twine
   ```

## Build the Package

1. Ensure the version number is updated in `pyproject.toml`
2. Build the distribution packages:
   ```bash
   python -m build
   ```
   This will create both source and wheel distributions in the `dist/` directory.

## Test the Package (Optional)

1. Upload to TestPyPI:
   ```bash
   twine upload --repository-url https://test.pypi.org/legacy/ dist/*
   ```
2. Install and test from TestPyPI:
   ```bash
   uv pip install --index-url https://test.pypi.org/simple/ --no-deps mcp-filesystem
   ```

## Publish to PyPI

1. Upload to PyPI:
   ```bash
   twine upload dist/*
   ```

## Create GitHub Release

1. Create a git tag for the version:
   ```bash
   git tag -a v0.2.0 -m "Version 0.2.0"
   git push origin v0.2.0
   ```
2. Create a new release on GitHub:
   - Go to the repository page on GitHub
   - Click on "Releases"
   - Click "Create a new release"
   - Select the tag you just created
   - Add release notes (use the relevant section from CHANGELOG.md)
   - Publish the release

## Verify Package Installation

After publishing, verify that the package can be installed:

```bash
uv pip install mcp-filesystem
```

## Troubleshooting

If you encounter issues when publishing:

1. **Upload errors**: Verify that the package name is not already in use on PyPI
2. **Invalid credentials**: Check your PyPI credentials in `~/.pypirc`
3. **Build errors**: Make sure `pyproject.toml` is correctly formatted