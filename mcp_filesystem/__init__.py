"""MCP Filesystem Server.

A Model Context Protocol server that provides secure access to the filesystem.
"""

__version__ = "0.1.0"

from .server import mcp


def main() -> None:
    """Main entry point for the package."""
    try:
        mcp.run()
    except KeyboardInterrupt:
        import sys

        print("\nShutting down...", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        import sys

        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


__all__ = ["mcp", "main"]
