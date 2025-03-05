# MCP Filesystem Server

[![License](https://img.shields.io/github/license/safurrier/mcp-filesystem.svg)](https://github.com/safurrier/mcp-filesystem/blob/main/LICENSE)

A powerful Model Context Protocol (MCP) server for filesystem operations that provides Claude and other MCP clients with secure access to files and directories.

## Features

- **Secure File Access**: Only allows operations within explicitly allowed directories
- **Comprehensive Operations**: Full set of file system capabilities
  - Standard operations (read, write, list, move, delete)
  - Enhanced operations (tree visualization, duplicate finding, etc.)
  - Advanced search with grep integration (uses ripgrep when available)
    - Context control (like grep's -A/-B/-C options) 
    - Result pagination for large result sets
  - Line-targeted operations with content verification and relative line numbers
- **Performance Optimized**:
  - Efficiently handles large files and directories
  - Ripgrep integration for blazing fast searches
  - Line-targeted operations to avoid loading entire files
- **Comprehensive Testing**: 75+ tests with behavior-driven approach
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Installation

### Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/mcp-filesystem.git
cd mcp-filesystem

# Install dependencies with uv
uv pip sync requirements.txt requirements-dev.txt
```

## Usage

### Running the Server

Run the server with access to specific directories:

```bash
# Using uv (recommended)
uv run run_server.py /path/to/dir1 /path/to/dir2

# Or using standard Python
python run_server.py /path/to/dir1 /path/to/dir2
```

#### Options

- `--transport` or `-t`: Transport protocol (stdio or sse, default: stdio)
- `--port` or `-p`: Port for SSE transport (default: 8000)
- `--debug` or `-d`: Enable debug logging

### Using with MCP Inspector

For interactive testing and debugging with the MCP Inspector:

```bash
# Basic usage
npx @modelcontextprotocol/inspector uv run run_server.py /path/to/directory

# With SSE transport
npx @modelcontextprotocol/inspector uv run run_server.py /path/to/directory --transport sse --port 8080

# With debug output
npx @modelcontextprotocol/inspector uv run run_server.py /path/to/directory --debug
```

This server has been built with the FastMCP SDK for better alignment with current MCP best practices. It uses an efficient component caching system and direct decorator pattern.

## Claude Desktop Integration

Edit your Claude Desktop config file to integrate MCP-Filesystem:

**Config file location:**
- On macOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
- On Windows: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mcp-filesystem": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/mcp-filesystem/repo",
        "run",
        "run_server.py"
      ]
    }
  }
}
```

To allow access to specific directories, add them as additional arguments:

```json
{
  "mcpServers": {
    "mcp-filesystem": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/mcp-filesystem/repo",
        "run",
        "run_server.py",
        "/Users/yourusername/Projects",
        "/Users/yourusername/Documents"
      ]
    }
  }
}
```

> Note: The `--directory` flag is important as it tells uv where to find the repository containing run_server.py. Replace `/path/to/mcp-filesystem/repo` with the actual path to where you cloned the repository on your system.

## Development

### Running Tests

```bash
# Run all tests
uv run -m pytest tests/

# Run specific test file
uv run -m pytest tests/test_operations_unit.py

# Run with coverage
uv run -m pytest tests/ --cov=mcp_filesystem --cov-report=term-missing
```

### Code Style and Quality

```bash
# Format code
uv run -m ruff format mcp_filesystem

# Lint code
uv run -m ruff check --fix mcp_filesystem

# Type check
uv run -m mypy mcp_filesystem

# Run all checks
uv run -m ruff format mcp_filesystem && \
uv run -m ruff check --fix mcp_filesystem && \
uv run -m mypy mcp_filesystem && \
uv run -m pytest tests --cov=mcp_filesystem
```

## Available Tools

### Basic File Operations

- **read_file**: Read the complete contents of a file
- **read_multiple_files**: Read multiple files simultaneously
- **write_file**: Create a new file or overwrite an existing file
- **create_directory**: Create a new directory or ensure a directory exists
- **list_directory**: Get a detailed listing of files and directories
- **move_file**: Move or rename files and directories
- **get_file_info**: Retrieve detailed metadata about a file or directory
- **list_allowed_directories**: List directories the server is allowed to access

### Line-Targeted Operations

- **read_file_lines**: Read specific line ranges with offset/limit parameters
- **edit_file_at_line**: Make precise edits with content verification and relative line numbers
  - Support for content verification to prevent editing outdated content
  - Relative line numbers for easier regional editing
  - Multiple edit actions (replace, insert_before, insert_after, delete)
- **head_file**: Read the first N lines of a text file
- **tail_file**: Read the last N lines of a text file

### Advanced Search

- **grep_files**: Search for patterns in files with powerful options
  - Ripgrep integration for performance (with Python fallback)
  - Fine-grained context control (like grep's -A/-B/-C options)
  - Result pagination for large search results
  - RegEx support with case sensitivity and whole word options
- **search_files**: Search for files matching patterns with content search
- **directory_tree**: Get a recursive tree view of files and directories

### Analytics and Reporting

- **calculate_directory_size**: Calculate the total size of a directory
- **find_duplicate_files**: Find duplicate files by comparing content
- **compare_files**: Compare two text files and show differences
- **find_large_files**: Find files larger than a specified size
- **find_empty_directories**: Find empty directories

## Usage Examples

### Reading File Lines

```
Tool: read_file_lines
Arguments: {
  "path": "/path/to/file.txt",
  "offset": 99,        # 0-based indexing (line 100)
  "limit": 51,         # Read 51 lines
  "encoding": "utf-8"  # Optional encoding
}
```

### Searching for Content with Grep

```
Tool: grep_files
Arguments: {
  "path": "/path/to/search",
  "pattern": "function\\s+\\w+\\(",
  "is_regex": true,
  "context_before": 2,       # Show 2 lines before each match (like grep -B)
  "context_after": 5,        # Show 5 lines after each match (like grep -A)
  "include_patterns": ["*.js", "*.ts"],
  "results_offset": 0,       # Start from the first match
  "results_limit": 20        # Show at most 20 matches
}
```

### Line-Targeted Editing

```
Tool: edit_file_at_line
Arguments: {
  "path": "/path/to/file.txt",
  "line_edits": [
    {
      "line_number": 15,
      "action": "replace",
      "content": "This is the new content for line 15\n",
      "expected_content": "Original content of line 15\n" # Verify content before editing
    },
    {
      "line_number": 20,
      "action": "delete"
    }
  ],
  "offset": 0,                           # Start considering lines from this offset
  "relative_line_numbers": false,        # Whether line numbers are relative to offset
  "abort_on_verification_failure": true, # Stop on verification failure
  "dry_run": true                        # Preview changes without applying
}
```

### Finding Duplicate Files

```
Tool: find_duplicate_files
Arguments: {
  "path": "/path/to/search",
  "recursive": true,
  "min_size": 1024,
  "format": "text"
}
```

## Efficient Workflow

The tools are designed to work together efficiently:

1. Use `grep_files` to find relevant content with precise context control
   - Fine-grained control over context lines before/after matches
   - Paginate through large result sets efficiently
2. Examine specific sections with `read_file_lines` using offset/limit
   - Zero-based indexing with simple offset/limit parameters
   - Control exactly how many lines to read
3. Make targeted edits with `edit_file_at_line` with content verification
   - Verify content hasn't changed before editing
   - Use relative line numbers for regional editing
   - Multiple edit actions in a single operation

This workflow allows Claude to work effectively even with very large codebases by focusing on just the relevant parts while ensuring edits are safe and precise.

## Known Issues and Limitations

- **Regex Escaping**: When using regex patterns with special characters like `\d`, `\w`, or `\s`, you may need to double-escape backslashes (e.g., `\\d`, `\\w`, `\\s`). This is due to how JSON processes escape characters.
- **Path Resolution**: Always use absolute paths for the most consistent results. Relative paths might be interpreted relative to the server's working directory rather than the allowed directories.
- **Performance**: For large directories, operations like `find_duplicate_files` might take significant time to complete.
- **Permission Handling**: The server operates with the same permissions as the user running it. Make sure the server has appropriate permissions for the directories it needs to access.

## Security

The server enforces strict path validation to prevent access outside allowed directories:

- Only allows operations within explicitly allowed directories
- Provides protection against path traversal attacks
- Validates symlinks to ensure they don't point outside allowed directories
- Returns meaningful error messages without exposing sensitive information

## Performance Considerations

For best performance with grep functionality:

- Install [ripgrep](https://github.com/BurntSushi/ripgrep#installation) (`rg`)
- The server automatically uses ripgrep if available, with a Python fallback

## License

[MIT License](LICENSE)
