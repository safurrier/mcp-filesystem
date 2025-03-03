# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Grep functionality exposed through MCP
  - Support for ripgrep with Python fallback
  - Comprehensive search with regex, context, and pattern exclusion
  - Enhanced context control with separate before/after line parameters (like grep's -A/-B options)
  - Results pagination with offset/limit parameters
- Line-targeted file operations
  - `read_file_lines` with offset/limit paradigm for precise line access
  - `edit_file_at_line` with content verification and relative line number support
- Integration between grep and targeted operations for efficient workflow
- Documentation of type safety issues and guidance in CLAUDE.md
- Comprehensive test suite following pragmatic test-driven development approach
  - Smoke tests for critical user paths (read, write, grep, edit)
  - Integration tests with real temporary filesystem
  - End-to-end tests verifying server API to filesystem flow
  - Test data factories for sample data generation
  - Clean fixtures with proper dependency isolation
  - Mocks at external boundaries for faster test execution
  - Verification of actual functionality with real files

### Changed
- Improved Python compatibility (requires 3.10+)
- Enhanced server file operations with more granular edit capability
- Changed line-targeting API from 1-based to 0-based indexing with offset/limit paradigm
- Added content verification to file editing operations
- Added relative line numbers support for more flexible line editing
- Enhanced grep functionality with better context control and pagination
- Improved code safety with proper null checks for Context parameters
- Enhanced type safety with proper use of Optional types

### Fixed
- Integrated targeted operations and grep functionality into the main codebase
- Connected all components in the server implementation
- Fixed unsafe comparison between int and None
- Improved anyio.to_thread.run_sync usage with functools.partial
- Fixed context_before type mismatch in grep.py
- Properly typed transport parameter with Literal
- Fixed all type errors in server.py, operations.py, advanced.py, and grep.py
- Added type annotations for result variables and function parameters
- Fixed `Dict` type incompatibility issue in advanced.py
- Added missing imports from typing module (Any, Mapping)
- Fixed read_file_lines bug that caused it to read beyond the requested line range
- Fixed edit_file_at_line to properly handle content verification and relative line numbers
- Fixed grep pagination to properly slice result sets
- Improved test reliability by focusing on behavior rather than implementation details
- Fixed inconsistent test expectations to match actual API semantics

## [0.1.0] - 2025-03-02
- Initial project setup
- Basic file operations implementation
- Security framework for file access
- Server structure and MCP integration