#!/usr/bin/env python
"""
Simple entry point to run the MCP filesystem server.
Usage: uv run run_server.py [dir1] [dir2] ...

For use with MCP Inspector or Claude Desktop:
- Command: uv
- Arguments: --directory /path/to/mcp-filesystem run mcp-filesystem run

Note: The trailing 'run' is required as it specifies the subcommand to execute.
"""

import sys
from mcp_filesystem.__main__ import app

if __name__ == "__main__":
    sys.exit(app())