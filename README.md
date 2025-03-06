# MCP Filesystem Server

[![License](https://img.shields.io/github/license/safurrier/mcp-filesystem.svg)](https://github.com/safurrier/mcp-filesystem/blob/main/LICENSE)

A powerful Model Context Protocol (MCP) server for filesystem operations optimized for intelligent interaction with large files and filesystems. It provides secure access to files and directories with smart context management to maximize efficiency when working with extensive data.

## Why MCP-Filesystem?

- **Smart Context Management**: Work efficiently with large files and filesystems
  - Partial reading to focus only on relevant content
  - Precise context control for finding exactly what you need
  - Token-efficient search results with pagination
  - Multi-file operations to reduce request overhead

- **Intelligent File Operations**:
  - Line-targeted reading with configurable context windows
  - Advanced editing with content verification to prevent conflicts
  - Fine-grained search capabilities that exceed standard grep
  - Relative line references for precise file manipulation

## Key Features

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

## Quickstart Guide

### 1. Clone and Setup

First, install uv if you haven't already:

```bash
# Install uv using the official installer
curl -fsSL https://raw.githubusercontent.com/astral-sh/uv/main/install.sh | bash

# Or with pipx
pipx install uv
```

Then clone the repository and install dependencies:

```bash
# Clone the repository
git clone https://github.com/safurrier/mcp-filesystem.git
cd mcp-filesystem

# Install dependencies with uv
uv pip sync requirements.txt requirements-dev.txt
```

### 2. Get Absolute Paths

You'll need absolute paths both for the repository location and any directories you want to access:

```bash
# Get the absolute path to the repository
REPO_PATH=$(pwd)
echo "Repository path: $REPO_PATH"

# Get absolute paths to directories you want to access
realpath ~/Documents
realpath ~/Downloads
# Or on systems without realpath:
echo "$(cd ~/Documents && pwd)"
```

### 3. Configure Claude Desktop

Open your Claude Desktop configuration file:
- On macOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
- On Windows: `%APPDATA%/Claude/claude_desktop_config.json`

Add the following configuration (substitute your actual paths):

```json
{
  "mcpServers": {
    "mcp-filesystem": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/mcp-filesystem",
        "run",
        "run_server.py",
        "/absolute/path/to/dir1",
        "/absolute/path/to/dir2"
      ]
    }
  }
}
```

> **Important**: All paths must be absolute (full paths from root directory).
> Use `realpath` or `pwd` to ensure you have the correct absolute paths.

### 4. Restart Claude Desktop

After saving your configuration, restart Claude Desktop for the changes to take effect.

## Installation

## Usage

### Watch Server Logs

You can monitor the server logs from Claude Desktop with:

```bash
# On macOS
tail -n 20 -f ~/Library/Logs/Claude/mcp-server-mcp-filesystem.log

# On Windows (PowerShell)
Get-Content -Path "$env:APPDATA\Claude\Logs\mcp-server-mcp-filesystem.log" -Tail 20 -Wait
```

This is particularly useful for debugging issues or seeing exactly what Claude is requesting.

### Running the Server

Run the server with access to specific directories:

```bash
# Using uv (recommended)
uv run run_server.py /path/to/dir1 /path/to/dir2

# Or using standard Python
python run_server.py /path/to/dir1 /path/to/dir2

# Example with actual paths
uv run run_server.py /Users/username/Documents /Users/username/Downloads
```

#### Options

- `--transport` or `-t`: Transport protocol (stdio or sse, default: stdio)
- `--port` or `-p`: Port for SSE transport (default: 8000)
- `--debug` or `-d`: Enable debug logging
- `--version` or `-v`: Show version information

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

## Efficient Workflow for Large Files and Filesystems

MCP-Filesystem is designed for intelligent interaction with large files and complex filesystems:

1. **Smart Context Discovery**
   - Use `grep_files` to find exactly what you need with precise context control
   - Fine-grained control over context lines before/after matches prevents token waste
   - Paginate through large result sets efficiently without overwhelming token limits
   - Ripgrep integration handles massive filesystems with millions of files and lines

2. **Targeted Reading**
   - Examine only relevant sections with `read_file_lines` using offset/limit
   - Zero-based indexing with simple offset/limit parameters for precise content retrieval
   - Control exactly how many lines to read to maximize token efficiency
   - Read multiple files simultaneously to reduce round-trips

3. **Precise Editing**
   - Make targeted edits with `edit_file_at_line` with content verification
   - Verify content hasn't changed before editing to prevent conflicts
   - Use relative line numbers for regional editing in complex files
   - Multiple edit actions in a single operation for complex changes
   - Dry-run capability to preview changes before applying

4. **Advanced Analysis**
   - Use specialized tools like `find_duplicate_files` and `compare_files`
   - Generate directory trees with `directory_tree` for quick navigation
   - Identify problematic areas with `find_large_files` and `find_empty_directories`

This workflow is particularly valuable for AI-powered tools that need to work with large files and filesystems. For example, Claude and other advanced AI assistants can leverage these capabilities to efficiently navigate codebases, analyze log files, or work with any large text-based datasets while maintaining token efficiency.

## Advantages Over Standard Filesystem MCP Servers

Unlike basic filesystem MCP servers, MCP-Filesystem offers:

1. **Token Efficiency**
   - Smart line-targeted operations avoid loading entire files into context
   - Pagination controls for large results prevent context overflow
   - Precise grep with context controls (not just whole file searches)
   - Multi-file reading reduces round-trip requests

2. **Intelligent Editing**
   - Content verification to prevent edit conflicts
   - Line-targeted edits that don't require the entire file
   - Relative line number support for easier regional editing
   - Dry-run capability to preview changes before applying

3. **Advanced Search**
   - Ripgrep integration for massive filesystem performance
   - Context-aware results (not just matches)
   - Fine-grained control over what gets returned
   - Pattern-based file finding with exclusion support

4. **Additional Utilities**
   - File comparison and deduplication
   - Directory size calculation and analysis
   - Empty directory identification
   - Tree-based directory visualization

5. **Security Focus**
   - Robust path validation and sandboxing
   - Protection against path traversal attacks
   - Symlink validation and security
   - Detailed error reporting without sensitive exposure

## Known Issues and Limitations

- **Path Resolution**: Always use absolute paths for the most consistent results. Relative paths might be interpreted relative to the server's working directory rather than the allowed directories.
- **Performance**: For large directories, operations like `find_duplicate_files` or recusrive search might take significant time to complete.
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
