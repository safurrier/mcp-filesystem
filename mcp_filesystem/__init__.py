"""MCP Filesystem Server.

A Model Context Protocol server that provides secure access to the filesystem.
"""

__version__ = "0.1.0"

from .server import mcp

__all__ = ["mcp"]
