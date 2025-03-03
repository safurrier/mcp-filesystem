"""Command-line interface for the MCP Filesystem Server."""

import os
import sys
from typing import List, Optional

import typer
from typing_extensions import Annotated

from .server import mcp

app = typer.Typer(
    name="mcp-filesystem",
    help="MCP Filesystem Server",
    add_completion=False,
)


@app.command()
def run(
    directory: Annotated[
        Optional[List[str]],
        typer.Argument(
            help="Allowed directories (defaults to current directory if none provided)",
            show_default=False,
        ),
    ] = None,
    transport: Annotated[
        str,
        typer.Option(
            "--transport",
            "-t",
            help="Transport protocol to use",
        ),
    ] = "stdio",
    port: Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            help="Port for SSE transport",
        ),
    ] = 8000,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            "-d",
            help="Enable debug logging",
        ),
    ] = False,
    name: Annotated[
        Optional[str],
        typer.Option(
            "--name",
            "-n",
            help="Server name",
        ),
    ] = None,
) -> None:
    """Run the MCP Filesystem Server.

    By default, the server will only allow access to the current directory.
    You can specify one or more allowed directories as arguments.
    """
    # Set allowed directories in environment for the server to pick up
    if directory:
        os.environ["MCP_ALLOWED_DIRS"] = os.pathsep.join(directory)

    # Set debug mode if requested
    if debug:
        os.environ["FASTMCP_LOG_LEVEL"] = "DEBUG"

    # Setting custom name is not supported with FastMCP
    # Just log the name for now
    if name:
        print(f"Using server name: {name}")

    try:
        if transport.lower() == "sse":
            os.environ["FASTMCP_PORT"] = str(port)
            mcp.run(transport="sse")
        else:
            mcp.run(transport="stdio")
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


@app.command()
def version() -> None:
    """Show version information."""
    try:
        from importlib.metadata import version as get_version

        version = get_version("mcp-filesystem")
    except ImportError:
        version = "unknown"

    print(f"MCP Filesystem Server v{version}")
    print("A Model Context Protocol server for filesystem operations")


if __name__ == "__main__":
    app()
