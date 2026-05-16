# MCP Filesystem Server

MCP Filesystem Server lets an MCP client read, search, and edit files inside directories you explicitly allow. It is useful when Claude Desktop or another MCP client needs filesystem access with path sandboxing, line-range reads, grep-style search, and edit previews.

The server does not grant whole-disk access. At startup you pass one or more allowed directories; every tool call is validated against those roots.

## Quick start from a source checkout

This README documents running the server from this repository. Published-package installation is not verified here.

```bash
git clone https://github.com/safurrier/mcp-filesystem.git
cd mcp-filesystem
uv sync --frozen
uv run run_server.py --version
```

Success signal:

```text
MCP Filesystem Server v0.2.0
A Model Context Protocol server for filesystem operations
```

`uv sync --frozen` installs the locked dependencies into `.venv` in the checkout.

To see the command-line options without starting an MCP session:

```bash
uv run run_server.py --help
```

The main entry points in this repo are:

- `uv run run_server.py ...` — direct script used by tests and the Claude Desktop examples below.
- `uv run mcp-filesystem ...` — installed console script with the same Typer CLI.

## Connect it to Claude Desktop

Use absolute paths for both the repository and the directories you want the server to access:

```bash
REPO_PATH=$(pwd)
PROJECTS_PATH=$(cd ~/Projects && pwd)
DOCUMENTS_PATH=$(cd ~/Documents && pwd)
printf 'repo=%s\nprojects=%s\ndocuments=%s\n' "$REPO_PATH" "$PROJECTS_PATH" "$DOCUMENTS_PATH"
```

Edit Claude Desktop's config file:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add one server entry, replacing the example paths with your own absolute paths:

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
        "/absolute/path/to/allowed-dir-1",
        "/absolute/path/to/allowed-dir-2"
      ]
    }
  }
}
```

Restart Claude Desktop after saving the file.

Claude-side success signals:

- The MCP server named `mcp-filesystem` appears in Claude Desktop's MCP tools.
- The tool list includes `list_allowed_directories`, `read_file`, `grep_files`, and `edit_file_at_line`.
- Calling `list_allowed_directories` returns only the directories you passed in the config.

If the server does not appear, watch the Claude Desktop MCP log:

```bash
# macOS
tail -n 50 -f ~/Library/Logs/Claude/mcp-server-mcp-filesystem.log

# Windows PowerShell
Get-Content -Path "$env:APPDATA\Claude\Logs\mcp-server-mcp-filesystem.log" -Tail 50 -Wait
```

## Run the server manually

The server uses stdio by default, which is what MCP clients such as Claude Desktop expect:

```bash
uv run run_server.py /absolute/path/to/dir1 /absolute/path/to/dir2
```

If you do not pass directories, the server allows the current working directory.

Options verified from the CLI:

| Option | Meaning |
| --- | --- |
| `--transport`, `-t` | Transport protocol. Default: `stdio`. Use `sse` for SSE. |
| `--port`, `-p` | Port for SSE transport. Default: `8000`. |
| `--debug`, `-d` | Enable debug logging through `FASTMCP_LOG_LEVEL=DEBUG`. |
| `--version`, `-v` | Print version information and exit. |
| `--help` | Print CLI help and exit. |

For MCP Inspector testing, run from a checkout:

```bash
npx @modelcontextprotocol/inspector uv run run_server.py /absolute/path/to/test-dir
```

The Inspector command may download Node packages through `npx` if they are not already installed.

## How access control works

- Allowed roots come from positional CLI arguments, or from `MCP_ALLOWED_DIRS` when the CLI sets it.
- If neither is set, the current working directory is the only allowed root.
- Paths are validated before filesystem operations run.
- Symlinks are checked so a path inside an allowed root cannot point outside it.
- The server runs with the operating-system permissions of the user that started it.

Practical rule: pass the narrowest directory that contains the files you want Claude to work with. Do not pass `/`, your full home directory, or a secrets directory unless you mean to expose it to the MCP client.

## MCP tools

Tool names below are taken from `mcp_filesystem/server.py`.

### Discovery and read-only file access

| Tool | Use it for |
| --- | --- |
| `list_allowed_directories` | Show the sandbox roots available to this server process. |
| `list_directory` | List files and directories, with optional hidden-file and pattern filtering. |
| `get_file_info` | Return file or directory metadata. |
| `read_file` | Read one complete file. |
| `read_multiple_files` | Read several complete files in one tool call. |
| `read_file_lines` | Read a line range with `offset` and `limit`. |
| `head_file` | Read the first N lines of a text file. |
| `tail_file` | Read the last N lines of a text file. |
| `directory_tree` | Return a recursive directory tree with depth and pattern controls. |

### Search

| Tool | Use it for |
| --- | --- |
| `grep_files` | Search file contents with literal or regex matching, context lines, pagination, size limits, and optional JSON output. Uses ripgrep when available and falls back to Python. |
| `search_files` | Find files or directories by glob pattern, optionally requiring content matches. |

### Mutating filesystem operations

| Tool | Use it for |
| --- | --- |
| `write_file` | Create or overwrite a file. Can create parent directories when requested. |
| `create_directory` | Create a directory, optionally including parents. |
| `move_file` | Move or rename a file or directory. |
| `edit_file` | Apply old-text/new-text edits and return a git-style diff. Supports `dry_run`. |
| `edit_file_at_line` | Apply line-targeted edits. Supports verification, relative line numbers, abort-on-verification-failure, and `dry_run`. |

Start mutating work with `dry_run: true` where the tool supports it. For `write_file`, `create_directory`, and `move_file`, choose a temporary test directory first if you are checking behavior.

### Analysis and cleanup helpers

| Tool | Use it for |
| --- | --- |
| `calculate_directory_size` | Calculate directory size as human-readable text, bytes, or JSON. |
| `find_duplicate_files` | Find duplicate files by size and content hash. |
| `compare_files` | Compare two text files and return similarity plus diff output. |
| `find_large_files` | Find files above a size threshold. |
| `find_empty_directories` | Find empty directories. |

These helpers can scan many files. Use narrow allowed directories and result limits for large trees.

## Common workflows

### Read a specific part of a large file

Use `grep_files` to find a match, then `read_file_lines` to inspect the surrounding range. `read_file_lines` uses a 0-based `offset` and a maximum `limit`.

```json
{
  "path": "/absolute/path/to/file.log",
  "offset": 1200,
  "limit": 80,
  "encoding": "utf-8"
}
```

### Search with context and pagination

```json
{
  "path": "/absolute/path/to/project",
  "pattern": "def main",
  "is_regex": false,
  "context_before": 2,
  "context_after": 4,
  "include_patterns": ["*.py"],
  "results_offset": 0,
  "results_limit": 20
}
```

### Preview a line-targeted edit

```json
{
  "path": "/absolute/path/to/file.txt",
  "line_edits": [
    {
      "line_number": 15,
      "action": "replace",
      "content": "replacement text\n",
      "expected_content": "old text\n"
    }
  ],
  "abort_on_verification_failure": true,
  "dry_run": true
}
```

Then repeat with `dry_run: false` only after the preview is correct.

## Development

Set up the checkout:

```bash
uv sync --frozen --all-extras
```

Run focused checks while editing:

```bash
uv run -m pytest tests/test_cli.py
uv run -m pytest tests/test_server_unit.py
uv run -m ruff check mcp_filesystem tests
uv run -m mypy mcp_filesystem
```

The Makefile also provides maintainer workflows:

```bash
make setup   # compiles requirements, creates .venv, syncs deps, installs pre-commit hooks
make check   # setup, lint with --fix, format, tests with coverage, mypy
```

`make check` mutates local files because it may update requirements, install hooks, apply Ruff fixes, and write coverage data.

## Troubleshooting

### Claude Desktop cannot start the server

Do this:

1. Run `uv run run_server.py --version` from the checkout.
2. Confirm the Claude config uses an absolute path after `--directory`.
3. Confirm every allowed directory path is absolute and exists.
4. Check the Claude MCP log shown above.

Do not use relative paths in the Claude config; they may be resolved relative to the client process, not this repository.

### A file outside the allowed directory is rejected

That is expected. Restart the MCP server with the narrowest additional allowed root that contains the file.

### Search is slower than expected

Install `ripgrep` (`rg`). The server uses ripgrep when it is available and falls back to Python search otherwise.

### A mutating tool changed the wrong file

Prefer `edit_file_at_line` with `expected_content`, `abort_on_verification_failure: true`, and `dry_run: true` before applying changes. For whole-file replacement, use `read_file` or `get_file_info` first so the client has the current path and content.

## Further reading

- [CONTRIBUTING.md](CONTRIBUTING.md) — contribution flow and maintainer expectations.
- [CHANGELOG.md](CHANGELOG.md) — notable changes and API behavior notes.
- [LICENSE](LICENSE) — MIT license.
