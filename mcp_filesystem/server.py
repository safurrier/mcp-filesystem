"""MCP Filesystem Server.

This module provides a Model Context Protocol server for filesystem operations,
allowing Claude and other MCP clients to safely access and manipulate files.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, List, Optional, Union, Dict

from fastmcp import FastMCP, Context
from fastmcp.utilities.logging import get_logger

from .advanced import AdvancedFileOperations
from .operations import FileOperations
from .security import PathValidator
from .grep import GrepTools

logger = get_logger(__name__)


def get_allowed_dirs() -> List[Union[str, Path]]:
    """Get the list of allowed directories from environment or arguments.

    Returns:
        List of allowed directory paths
    """
    allowed_dirs = os.environ.get("MCP_ALLOWED_DIRS", "").split(os.pathsep)

    # Add any command-line arguments as allowed directories
    if len(sys.argv) > 1:
        allowed_dirs.extend(sys.argv[1:])

    # If no allowed directories specified, use current directory
    if not allowed_dirs or all(not d for d in allowed_dirs):
        allowed_dirs = [os.getcwd()]

    # Cast strings and filter empty strings
    return [d for d in allowed_dirs if d]


# Create component initialization function with caching
_components_cache: Dict[str, Any] = {}


def get_components() -> Dict[str, Any]:
    """Initialize and return shared components.

    Returns cached components if already initialized.

    Returns:
        Dictionary with initialized components
    """
    # Return cached components if available
    if _components_cache:
        return _components_cache

    # Initialize components
    allowed_dirs_typed: List[Union[str, Path]] = get_allowed_dirs()
    validator = PathValidator(allowed_dirs_typed)
    operations = FileOperations(validator)
    advanced = AdvancedFileOperations(validator, operations)
    grep = GrepTools(validator)

    # Store in cache
    _components = {
        "validator": validator,
        "operations": operations,
        "advanced": advanced,
        "grep": grep,
        "allowed_dirs": validator.get_allowed_dirs(),
    }

    # Update cache
    _components_cache.update(_components)

    logger.info(
        f"Initialized filesystem components with allowed directories: {validator.get_allowed_dirs()}"
    )

    return _components


# Create the FastMCP instance
mcp = FastMCP(
    name="Filesystem MCP Server",
    instructions="Provides secure access to the filesystem through MCP",
    dependencies=[],
)


@mcp.tool()
async def read_file(path: str, ctx: Context, encoding: str = "utf-8") -> str:
    """Read the complete contents of a file.

    Args:
        path: Path to the file
        encoding: File encoding (default: utf-8)
        ctx: MCP context

    Returns:
        File contents as a string
    """
    try:
        components = get_components()
        return await components["operations"].read_file(path, encoding)
    except Exception as e:
        return f"Error reading file: {str(e)}"


@mcp.tool()
async def read_multiple_files(
    paths: List[str], ctx: Context, encoding: str = "utf-8"
) -> Dict[str, str]:
    """Read multiple files at once.

    Args:
        paths: List of file paths to read
        encoding: File encoding (default: utf-8)
        ctx: MCP context

    Returns:
        Dictionary mapping file paths to contents or error messages
    """
    try:
        components = get_components()
        results = await components["operations"].read_multiple_files(paths, encoding)

        # Convert exceptions to strings for JSON serialization
        formatted_results = {}
        for path, result in results.items():
            if isinstance(result, Exception):
                formatted_results[path] = f"Error: {str(result)}"
            else:
                formatted_results[path] = result

        return formatted_results
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def write_file(
    path: str,
    content: str,
    ctx: Context,
    encoding: str = "utf-8",
    create_dirs: bool = False,
) -> str:
    """Create a new file or overwrite an existing file with new content.

    Args:
        path: Path to write to
        content: Content to write
        encoding: File encoding (default: utf-8)
        create_dirs: Whether to create parent directories if they don't exist
        ctx: MCP context

    Returns:
        Success or error message
    """
    try:
        components = get_components()
        await components["operations"].write_file(path, content, encoding, create_dirs)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@mcp.tool()
async def create_directory(
    path: str,
    ctx: Context,
    parents: bool = True,
    exist_ok: bool = True,
) -> str:
    """Create a new directory or ensure a directory exists.

    Args:
        path: Path to the directory
        parents: Create parent directories if they don't exist
        exist_ok: Don't raise an error if directory already exists
        ctx: MCP context

    Returns:
        Success or error message
    """
    try:
        components = get_components()
        await components["operations"].create_directory(path, parents, exist_ok)
        return f"Successfully created directory {path}"
    except Exception as e:
        return f"Error creating directory: {str(e)}"


@mcp.tool()
async def list_directory(
    path: str,
    ctx: Context,
    include_hidden: bool = False,
    pattern: Optional[str] = None,
    format: str = "text",
) -> str:
    """Get a detailed listing of files and directories in a path.

    Args:
        path: Path to the directory
        include_hidden: Whether to include hidden files (starting with .)
        pattern: Optional glob pattern to filter entries
        format: Output format ('text' or 'json')
        ctx: MCP context

    Returns:
        Formatted directory listing
    """
    try:
        components = get_components()
        if format.lower() == "json":
            entries = await components["operations"].list_directory(
                path, include_hidden, pattern
            )
            return json.dumps(entries, indent=2)
        else:
            return await components["operations"].list_directory_formatted(
                path, include_hidden, pattern
            )
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@mcp.tool()
async def move_file(
    source: str,
    destination: str,
    ctx: Context,
    overwrite: bool = False,
) -> str:
    """Move or rename files and directories.

    Args:
        source: Source path
        destination: Destination path
        overwrite: Whether to overwrite existing destination
        ctx: MCP context

    Returns:
        Success or error message
    """
    try:
        components = get_components()
        await components["operations"].move_file(source, destination, overwrite)
        return f"Successfully moved {source} to {destination}"
    except Exception as e:
        return f"Error moving file: {str(e)}"


@mcp.tool()
async def get_file_info(path: str, ctx: Context, format: str = "text") -> str:
    """Retrieve detailed metadata about a file or directory.

    Args:
        path: Path to the file or directory
        format: Output format ('text' or 'json')
        ctx: MCP context

    Returns:
        Formatted file information
    """
    try:
        components = get_components()
        info = await components["operations"].get_file_info(path)

        if format.lower() == "json":
            return json.dumps(info.to_dict(), indent=2)
        else:
            return str(info)
    except Exception as e:
        return f"Error getting file info: {str(e)}"


@mcp.tool()
async def list_allowed_directories(ctx: Context) -> str:
    """Returns the list of directories that this server is allowed to access.

    Args:
        ctx: MCP context

    Returns:
        List of allowed directories
    """
    components = get_components()
    allowed_dirs = components["allowed_dirs"]
    return f"Allowed directories:\n{os.linesep.join(allowed_dirs)}"


@mcp.tool()
async def edit_file(
    path: str,
    edits: List[Dict[str, str]],
    ctx: Context,
    encoding: str = "utf-8",
    dry_run: bool = False,
) -> str:
    """Make line-based edits to a text file.

    Args:
        path: Path to the file
        edits: List of {oldText, newText} dictionaries
        encoding: Text encoding (default: utf-8)
        dry_run: If True, return diff but don't modify file
        ctx: MCP context

    Returns:
        Git-style diff showing changes
    """
    try:
        components = get_components()
        return await components["operations"].edit_file(path, edits, encoding, dry_run)
    except Exception as e:
        return f"Error editing file: {str(e)}"


@mcp.tool()
async def head_file(
    path: str,
    ctx: Context,
    lines: int = 10,
    encoding: str = "utf-8",
) -> str:
    """Read the first N lines of a text file.

    Args:
        path: Path to the file
        lines: Number of lines to read (default: 10)
        encoding: Text encoding (default: utf-8)
        ctx: MCP context

    Returns:
        First N lines of the file
    """
    try:
        components = get_components()
        content = await components["operations"].head_file(path, lines, encoding)
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


@mcp.tool()
async def tail_file(
    path: str,
    ctx: Context,
    lines: int = 10,
    encoding: str = "utf-8",
) -> str:
    """Read the last N lines of a text file.

    Args:
        path: Path to the file
        lines: Number of lines to read (default: 10)
        encoding: Text encoding (default: utf-8)
        ctx: MCP context

    Returns:
        Last N lines of the file
    """
    try:
        components = get_components()
        content = await components["operations"].tail_file(path, lines, encoding)
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


@mcp.tool()
async def search_files(
    path: str,
    pattern: str,
    ctx: Context,
    recursive: bool = True,
    exclude_patterns: Optional[List[str]] = None,
    content_match: Optional[str] = None,
    max_results: int = 100,
    format: str = "text",
) -> str:
    """Recursively search for files and directories matching a pattern.

    Args:
        path: Starting directory
        pattern: Glob pattern to match against filenames
        recursive: Whether to search subdirectories
        exclude_patterns: Optional patterns to exclude
        content_match: Optional text to search within files
        max_results: Maximum number of results to return
        format: Output format ('text' or 'json')
        ctx: MCP context

    Returns:
        Search results
    """
    try:
        components = get_components()
        results = await components["operations"].search_files(
            path, pattern, recursive, exclude_patterns, content_match, max_results
        )

        if format.lower() == "json":
            return json.dumps(results, indent=2)

        # Format as text
        if not results:
            return "No matching files found"

        lines = []
        for item in results:
            is_dir = item.get("is_directory", False)
            type_label = "[DIR]" if is_dir else "[FILE]"
            size = f" ({item['size']:,} bytes)" if not is_dir else ""
            lines.append(f"{type_label} {item['path']}{size}")

        return f"Found {len(results)} matching files:\n\n" + "\n".join(lines)
    except Exception as e:
        return f"Error searching files: {str(e)}"


@mcp.tool()
async def directory_tree(
    path: str,
    ctx: Context,
    max_depth: int = 3,
    include_files: bool = True,
    pattern: Optional[str] = None,
    exclude_patterns: Optional[List[str]] = None,
    format: str = "text",
) -> str:
    """Get a recursive tree view of files and directories.

    Args:
        path: Root directory
        max_depth: Maximum recursion depth
        include_files: Whether to include files (not just directories)
        pattern: Optional glob pattern to filter entries
        exclude_patterns: Optional patterns to exclude
        format: Output format ('text' or 'json')
        ctx: MCP context

    Returns:
        Formatted directory tree
    """
    try:
        components = get_components()
        if format.lower() == "json":
            tree = await components["advanced"].directory_tree(
                path, max_depth, include_files, pattern, exclude_patterns
            )
            return json.dumps(tree, indent=2)
        else:
            tree_text = await components["advanced"].directory_tree_formatted(
                path, max_depth, include_files, pattern, exclude_patterns
            )
            return tree_text
    except Exception as e:
        return f"Error creating directory tree: {str(e)}"


@mcp.tool()
async def calculate_directory_size(
    path: str, ctx: Context, format: str = "human"
) -> str:
    """Calculate the total size of a directory recursively.

    Args:
        path: Directory path
        format: Output format ('human', 'bytes', or 'json')
        ctx: MCP context

    Returns:
        Directory size information
    """
    try:
        components = get_components()
        size_bytes = await components["advanced"].calculate_directory_size(path)

        if format.lower() == "bytes":
            return str(size_bytes)

        if format.lower() == "json":
            return json.dumps(
                {
                    "path": path,
                    "size_bytes": size_bytes,
                    "size_kb": round(size_bytes / 1024, 2),
                    "size_mb": round(size_bytes / (1024 * 1024), 2),
                    "size_gb": round(size_bytes / (1024 * 1024 * 1024), 2),
                },
                indent=2,
            )

        # Human readable format
        if size_bytes < 1024:
            return f"Directory size: {size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"Directory size: {size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"Directory size: {size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"Directory size: {size_bytes / (1024 * 1024 * 1024):.2f} GB"

    except Exception as e:
        return f"Error calculating directory size: {str(e)}"


@mcp.tool()
async def find_duplicate_files(
    path: str,
    ctx: Context,
    recursive: bool = True,
    min_size: int = 1,
    exclude_patterns: Optional[List[str]] = None,
    max_files: int = 1000,
    format: str = "text",
) -> str:
    """Find duplicate files by comparing file sizes and contents.

    Args:
        path: Starting directory
        recursive: Whether to search subdirectories
        min_size: Minimum file size to consider (bytes)
        exclude_patterns: Optional patterns to exclude
        max_files: Maximum number of files to scan
        format: Output format ('text' or 'json')
        ctx: MCP context

    Returns:
        Duplicate file information
    """
    try:
        components = get_components()
        duplicates = await components["advanced"].find_duplicate_files(
            path, recursive, min_size, exclude_patterns, max_files
        )

        if format.lower() == "json":
            return json.dumps(duplicates, indent=2)

        # Format as text
        if not duplicates:
            return "No duplicate files found"

        lines = []
        for file_hash, files in duplicates.items():
            lines.append(f"Hash: {file_hash}")
            for file_path in files:
                lines.append(f"  {file_path}")
            lines.append("")

        return f"Found {len(duplicates)} sets of duplicate files:\n\n" + "\n".join(
            lines
        )

    except Exception as e:
        return f"Error finding duplicate files: {str(e)}"


@mcp.tool()
async def compare_files(
    file1: str,
    file2: str,
    ctx: Context,
    encoding: str = "utf-8",
    format: str = "text",
) -> str:
    """Compare two text files and show differences.

    Args:
        file1: First file path
        file2: Second file path
        encoding: Text encoding (default: utf-8)
        format: Output format ('text' or 'json')
        ctx: MCP context

    Returns:
        Comparison results
    """
    try:
        components = get_components()
        result = await components["advanced"].compare_files(file1, file2, encoding)

        if format.lower() == "json":
            return json.dumps(result, indent=2)

        # Format as text
        similarity_pct = f"{result['similarity'] * 100:.1f}%"

        if result["are_identical"]:
            return "Files are identical (100% similarity)"

        lines = [
            f"Comparing {file1} with {file2}",
            f"Similarity: {similarity_pct}",
            f"Lines added: {result['added_lines']}",
            f"Lines removed: {result['removed_lines']}",
            "",
            "Diff:",
            result["diff"],
        ]

        return "\n".join(lines)

    except Exception as e:
        return f"Error comparing files: {str(e)}"


@mcp.tool()
async def find_large_files(
    path: str,
    ctx: Context,
    min_size_mb: float = 100,
    recursive: bool = True,
    max_results: int = 100,
    exclude_patterns: Optional[List[str]] = None,
    format: str = "text",
) -> str:
    """Find files larger than the specified size.

    Args:
        path: Starting directory
        min_size_mb: Minimum file size in megabytes
        recursive: Whether to search subdirectories
        max_results: Maximum number of results to return
        exclude_patterns: Optional patterns to exclude
        format: Output format ('text' or 'json')
        ctx: MCP context

    Returns:
        Large file information
    """
    try:
        components = get_components()
        results = await components["advanced"].find_large_files(
            path, min_size_mb, recursive, max_results, exclude_patterns
        )

        if format.lower() == "json":
            return json.dumps(results, indent=2)

        # Format as text
        if not results:
            return f"No files larger than {min_size_mb} MB found"

        lines = []
        for file in results:
            size_mb = file["size"] / (1024 * 1024)
            lines.append(f"{file['path']} - {size_mb:.2f} MB")

        return (
            f"Found {len(results)} files larger than {min_size_mb} MB:\n\n"
            + "\n".join(lines)
        )

    except Exception as e:
        return f"Error finding large files: {str(e)}"


@mcp.tool()
async def find_empty_directories(
    path: str,
    ctx: Context,
    recursive: bool = True,
    exclude_patterns: Optional[List[str]] = None,
    format: str = "text",
) -> str:
    """Find empty directories.

    Args:
        path: Starting directory
        recursive: Whether to search subdirectories
        exclude_patterns: Optional patterns to exclude
        format: Output format ('text' or 'json')
        ctx: MCP context

    Returns:
        Empty directory information
    """
    try:
        components = get_components()
        results = await components["advanced"].find_empty_directories(
            path, recursive, exclude_patterns
        )

        if format.lower() == "json":
            return json.dumps(results, indent=2)

        # Format as text
        if not results:
            return "No empty directories found"

        return f"Found {len(results)} empty directories:\n\n" + "\n".join(results)

    except Exception as e:
        return f"Error finding empty directories: {str(e)}"


@mcp.tool()
async def grep_files(
    path: str,
    pattern: str,
    ctx: Context,
    is_regex: bool = False,
    case_sensitive: bool = True,
    whole_word: bool = False,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    context_lines: int = 0,
    context_before: int = 0,
    context_after: int = 0,
    results_offset: int = 0,
    results_limit: Optional[int] = None,
    max_results: int = 1000,
    max_file_size_mb: float = 10,
    recursive: bool = True,
    max_depth: Optional[int] = None,
    count_only: bool = False,
    format: str = "text",
) -> str:
    """Search for pattern in files, similar to grep.

    Args:
        path: Starting directory or file path
        pattern: Text or regex pattern to search for
        is_regex: Whether to treat pattern as regex
        case_sensitive: Whether search is case sensitive
        whole_word: Match whole words only
        include_patterns: Only include files matching these patterns
        exclude_patterns: Exclude files matching these patterns
        context_lines: Number of lines to show before AND after matches (like grep -C)
        context_before: Number of lines to show BEFORE matches (like grep -B)
        context_after: Number of lines to show AFTER matches (like grep -A)
        results_offset: Start at Nth match (0-based, for pagination)
        results_limit: Return at most this many matches (for pagination)
        max_results: Maximum total matches to find during search
        max_file_size_mb: Skip files larger than this size
        recursive: Whether to search subdirectories
        max_depth: Maximum directory depth to recurse
        count_only: Only show match counts per file
        format: Output format ('text' or 'json')
        ctx: MCP context

    Returns:
        Search results
    """
    try:
        components = get_components()

        # Fix regex escaping - if is_regex is True, handle backslash escaping
        pattern_fixed = pattern
        if is_regex and "\\" in pattern:
            # For patterns coming from JSON where backslashes are escaped,
            # we need to convert double backslashes to single backslashes
            pattern_fixed = pattern.replace("\\\\", "\\")

        results = await components["grep"].grep_files(
            path,
            pattern_fixed,
            is_regex,
            case_sensitive,
            whole_word,
            include_patterns,
            exclude_patterns,
            context_lines,
            context_before,
            context_after,
            max_results,
            max_file_size_mb,
            recursive,
            max_depth,
            count_only,
            results_offset=results_offset,
            results_limit=results_limit,
        )

        if format.lower() == "json":
            return json.dumps(results.to_dict(), indent=2)
        else:
            # Format as text with appropriate options
            show_line_numbers = True
            show_file_names = True
            show_context = context_lines > 0
            highlight = True

            return results.format_text(
                show_line_numbers=show_line_numbers,
                show_file_names=show_file_names,
                count_only=count_only,
                show_context=show_context,
                highlight=highlight,
            )

    except Exception as e:
        return f"Error searching files: {str(e)}"


@mcp.tool()
async def read_file_lines(
    path: str,
    ctx: Context,
    offset: int = 0,
    limit: Optional[int] = None,
    encoding: str = "utf-8",
) -> str:
    """Read specific lines from a text file.

    Args:
        path: Path to the file
        offset: Line offset (0-based, starts at first line)
        limit: Maximum number of lines to read (None for all remaining)
        encoding: Text encoding (default: utf-8)
        ctx: MCP context

    Returns:
        File content and metadata
    """
    try:
        components = get_components()
        content, metadata = await components["operations"].read_file_lines(
            path, offset, limit, encoding
        )

        if not content:
            last_line_desc = "end" if limit is None else f"offset+{limit}"
            return f"No content found between offset {offset} and {last_line_desc}"

        # Calculate display lines (1-based for human readability)
        display_start = offset + 1
        display_end = offset + metadata["lines_read"]

        header = (
            f"File: {path}\n"
            f"Lines: {display_start} to {display_end} "
            f"(of {metadata['total_lines']} total)\n"
            f"----------------------------------------\n"
        )

        return header + content

    except Exception as e:
        return f"Error reading file lines: {str(e)}"


@mcp.tool()
async def edit_file_at_line(
    path: str,
    line_edits: List[Dict[str, Any]],
    ctx: Context,
    offset: int = 0,
    limit: Optional[int] = None,
    relative_line_numbers: bool = False,
    abort_on_verification_failure: bool = False,
    encoding: str = "utf-8",
    dry_run: bool = False,
) -> str:
    """Edit specific lines in a text file.

    Args:
        path: Path to the file
        line_edits: List of edits to apply. Each edit is a dict with:
            - line_number: Line number to edit (0-based if relative_line_numbers=True, otherwise 1-based)
            - action: "replace", "insert_before", "insert_after", "delete"
            - content: New content for replace/insert operations (optional for delete)
            - expected_content: (Optional) Expected content of the line being edited for verification
        offset: Line offset (0-based) to start considering lines
        limit: Maximum number of lines to consider
        relative_line_numbers: Whether line numbers in edits are relative to offset
        abort_on_verification_failure: Whether to abort all edits if any verification fails
        encoding: Text encoding (default: utf-8)
        dry_run: If True, returns what would be changed without modifying the file
        ctx: MCP context

    Returns:
        Edit results summary
    """
    try:
        components = get_components()
        results = await components["operations"].edit_file_at_line(
            path,
            line_edits,
            offset,
            limit,
            relative_line_numbers,
            abort_on_verification_failure,
            encoding,
            dry_run,
        )

        # Format as text summary
        mode = "Would apply" if dry_run else "Applied"

        # Check if we had verification failures that prevented editing
        if "success" in results and not results["success"]:
            summary = [
                f"Failed to edit {results['path']} due to content verification failures:",
                "",
            ]

            if "verification_failures" in results:
                for failure in results["verification_failures"]:
                    line_num = failure.get("line", "?")
                    action = failure.get("action", "?")
                    summary.append(f"Line {line_num}: {action} - Verification failed")
                    summary.append(f"  Expected: {failure.get('expected', '').strip()}")
                    summary.append(f"  Actual:   {failure.get('actual', '').strip()}")
                    summary.append("")

            if "message" in results:
                summary.append(f"Error: {results['message']}")

            return "\n".join(summary)

        # Normal success case
        summary = [
            f"{mode} {results['edits_applied']} edits to {results['path']}:",
            "",
        ]

        # Add verification warnings if any
        if "verification_failures" in results and results["verification_failures"]:
            summary.append(
                "Warning: Some content verification checks failed but edits were applied:"
            )
            for failure in results["verification_failures"]:
                line_num = failure.get("line", "?")
                summary.append(f"  Line {line_num}: Content did not match expected")
            summary.append("")

        for change in results["changes"]:
            line_num = change.get("line", "?")
            action = change.get("action", "?")
            orig_line_num = change.get("original_line_number", "")
            line_info = f"Line {line_num}"
            if relative_line_numbers and orig_line_num != "":
                line_info = f"Line {line_num} (relative: {orig_line_num})"

            if action == "replace":
                summary.append(f"{line_info}: Replaced")
                summary.append(f"  - {change.get('before', '').strip()}")
                summary.append(f"  + {change.get('after', '').strip()}")
            elif action == "insert_before":
                summary.append(f"{line_info}: Inserted before")
                summary.append(f"  + {change.get('content', '').strip()}")
            elif action == "insert_after":
                summary.append(f"{line_info}: Inserted after")
                summary.append(f"  + {change.get('content', '').strip()}")
            elif action == "delete":
                summary.append(f"{line_info}: Deleted")
                summary.append(f"  - {change.get('content', '').strip()}")

            if "error" in change:
                summary.append(f"  ! Error: {change['error']}")

            summary.append("")

        return "\n".join(summary)

    except Exception as e:
        return f"Error editing file: {str(e)}"


# Entry point for direct execution
if __name__ == "__main__":
    mcp.run()
