"""Base file operations for MCP filesystem server.

This module provides the core file operations used by the MCP server,
including reading, writing, listing, and moving files.
"""

import shutil
import stat
from datetime import datetime
from functools import partial  # Added for mypy compatibility with run_sync
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

import anyio
from mcp.server.fastmcp.utilities.logging import get_logger

from .security import PathValidator

logger = get_logger(__name__)


class FileInfo:
    """Information about a file or directory."""

    def __init__(self, path: Path):
        """Initialize with a file path.

        Args:
            path: Path to the file or directory

        Raises:
            FileNotFoundError: If the file or directory does not exist
        """
        self.path = path
        self.stat = path.stat()
        self.is_dir = path.is_dir()
        self.is_file = path.is_file()
        self.is_symlink = path.is_symlink()
        self.size = self.stat.st_size
        self.created = datetime.fromtimestamp(self.stat.st_ctime)
        self.modified = datetime.fromtimestamp(self.stat.st_mtime)
        self.accessed = datetime.fromtimestamp(self.stat.st_atime)
        self.name = path.name

        # Format permissions similar to Unix 'ls -l'
        mode = self.stat.st_mode
        self.permissions = "".join(
            [
                "r" if mode & stat.S_IRUSR else "-",
                "w" if mode & stat.S_IWUSR else "-",
                "x" if mode & stat.S_IXUSR else "-",
                "r" if mode & stat.S_IRGRP else "-",
                "w" if mode & stat.S_IWGRP else "-",
                "x" if mode & stat.S_IXGRP else "-",
                "r" if mode & stat.S_IROTH else "-",
                "w" if mode & stat.S_IWOTH else "-",
                "x" if mode & stat.S_IXOTH else "-",
            ]
        )

        # Numeric permissions in octal
        self.permissions_octal = oct(mode & 0o777)[2:]

    def to_dict(self) -> Dict:
        """Convert to dictionary.

        Returns:
            Dictionary with file information
        """
        return {
            "name": self.name,
            "path": str(self.path),
            "size": self.size,
            "created": self.created.isoformat(),
            "modified": self.modified.isoformat(),
            "accessed": self.accessed.isoformat(),
            "is_directory": self.is_dir,
            "is_file": self.is_file,
            "is_symlink": self.is_symlink,
            "permissions": self.permissions,
            "permissions_octal": self.permissions_octal,
        }

    def __str__(self) -> str:
        """Get string representation.

        Returns:
            Formatted string with file information
        """
        file_type = "Directory" if self.is_dir else "File"
        symlink_info = " (symlink)" if self.is_symlink else ""
        size_str = f"{self.size:,} bytes"

        return (
            f"{file_type}{symlink_info}: {self.path}\n"
            f"Size: {size_str}\n"
            f"Created: {self.created.isoformat()}\n"
            f"Modified: {self.modified.isoformat()}\n"
            f"Accessed: {self.accessed.isoformat()}\n"
            f"Permissions: {self.permissions} ({self.permissions_octal})"
        )


class FileOperations:
    """Core file operations with security validation."""

    def __init__(self, validator: PathValidator):
        """Initialize with a path validator.

        Args:
            validator: PathValidator for security checks
        """
        self.validator = validator

    async def read_file(self, path: Union[str, Path], encoding: str = "utf-8") -> str:
        """Read a text file.

        Args:
            path: Path to the file
            encoding: Text encoding (default: utf-8)

        Returns:
            File contents as string

        Raises:
            ValueError: If path is outside allowed directories
            FileNotFoundError: If file does not exist
            PermissionError: If file cannot be read
        """
        abs_path, allowed = await self.validator.validate_path(path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {path}")

        try:
            return await anyio.to_thread.run_sync(
                partial(abs_path.read_text, encoding=encoding)
            )
        except UnicodeDecodeError:
            raise ValueError(f"Cannot decode file as {encoding}: {path}")

    async def read_file_binary(self, path: Union[str, Path]) -> bytes:
        """Read a binary file.

        Args:
            path: Path to the file

        Returns:
            File contents as bytes

        Raises:
            ValueError: If path is outside allowed directories
            FileNotFoundError: If file does not exist
            PermissionError: If file cannot be read
        """
        abs_path, allowed = await self.validator.validate_path(path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {path}")

        return await anyio.to_thread.run_sync(partial(abs_path.read_bytes))

    async def write_file(
        self,
        path: Union[str, Path],
        content: Union[str, bytes],
        encoding: str = "utf-8",
        create_dirs: bool = False,
    ) -> None:
        """Write to a file.

        Args:
            path: Path to the file
            content: Content to write (string or bytes)
            encoding: Text encoding for string content
            create_dirs: Whether to create parent directories if they don't exist

        Raises:
            ValueError: If path is outside allowed directories
            PermissionError: If file cannot be written
        """
        abs_path, allowed = await self.validator.validate_path(path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {path}")

        # Create parent directories if requested
        if create_dirs:
            parent_dir = abs_path.parent
            if not parent_dir.exists():
                try:
                    await anyio.to_thread.run_sync(
                        partial(parent_dir.mkdir, parents=True)
                    )
                except (PermissionError, FileNotFoundError) as e:
                    raise ValueError(f"Cannot create parent directories: {e}")

        # Write content
        try:
            if isinstance(content, str):
                await anyio.to_thread.run_sync(
                    partial(abs_path.write_text, content, encoding=encoding)
                )
            else:
                await anyio.to_thread.run_sync(partial(abs_path.write_bytes, content))
        except PermissionError as e:
            raise ValueError(f"Cannot write to file: {e}")

    async def read_multiple_files(
        self, paths: List[Union[str, Path]], encoding: str = "utf-8"
    ) -> Dict[str, Union[str, Exception]]:
        """Read multiple files at once.

        Args:
            paths: List of file paths
            encoding: Text encoding (default: utf-8)

        Returns:
            Dictionary mapping file paths to contents or exceptions
        """
        # Explicitly type-annotate the results to help mypy
        results: Dict[str, Union[str, Exception]] = {}

        for path in paths:
            try:
                abs_path, allowed = await self.validator.validate_path(path)
                if not allowed:
                    # Create an error and store it
                    error_msg = f"Path outside allowed directories: {path}"
                    results[str(path)] = ValueError(error_msg)
                    continue

                content = await anyio.to_thread.run_sync(
                    partial(abs_path.read_text, encoding=encoding)
                )
                results[str(path)] = content
            except Exception as e:
                results[str(path)] = e

        return results

    async def create_directory(
        self, path: Union[str, Path], parents: bool = True, exist_ok: bool = True
    ) -> None:
        """Create a directory.

        Args:
            path: Path to the directory
            parents: Create parent directories if they don't exist
            exist_ok: Don't raise an error if directory already exists

        Raises:
            ValueError: If path is outside allowed directories
            PermissionError: If directory cannot be created
        """
        abs_path, allowed = await self.validator.validate_path(path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {path}")

        try:
            # Using partial to help mypy understand we're passing args to mkdir, not run_sync
            await anyio.to_thread.run_sync(
                partial(abs_path.mkdir, parents=parents, exist_ok=exist_ok)
            )
        except FileExistsError:
            if not exist_ok:
                raise ValueError(f"Directory already exists: {path}")
        except PermissionError as e:
            raise ValueError(f"Cannot create directory: {e}")

    async def list_directory(
        self,
        path: Union[str, Path],
        include_hidden: bool = False,
        pattern: Optional[str] = None,
    ) -> List[Dict]:
        """List directory contents.

        Args:
            path: Path to the directory
            include_hidden: Whether to include hidden files (starting with .)
            pattern: Optional glob pattern to filter files

        Returns:
            List of file/directory information dictionaries

        Raises:
            ValueError: If path is outside allowed directories or not a directory
            PermissionError: If directory cannot be read
        """
        abs_path, allowed = await self.validator.validate_path(path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {path}")

        if not abs_path.is_dir():
            raise ValueError(f"Not a directory: {path}")

        results = []

        try:
            entries = await anyio.to_thread.run_sync(list, abs_path.iterdir())

            for entry in entries:
                # Skip hidden files if not requested
                if not include_hidden and entry.name.startswith("."):
                    continue

                # Apply pattern filter if specified
                if pattern and not entry.match(pattern):
                    continue

                try:
                    info = FileInfo(entry)
                    results.append(info.to_dict())
                except (PermissionError, FileNotFoundError):
                    # Skip files we can't access
                    pass

            return results

        except PermissionError as e:
            raise ValueError(f"Cannot read directory: {e}")

    async def list_directory_formatted(
        self,
        path: Union[str, Path],
        include_hidden: bool = False,
        pattern: Optional[str] = None,
    ) -> str:
        """List directory contents in a formatted string.

        Args:
            path: Path to the directory
            include_hidden: Whether to include hidden files
            pattern: Optional glob pattern to filter files

        Returns:
            Formatted string with directory contents
        """
        entries = await self.list_directory(path, include_hidden, pattern)

        if not entries:
            return "Directory is empty"

        # Format the output
        result = []
        for entry in sorted(entries, key=lambda x: (not x["is_directory"], x["name"])):
            prefix = "[DIR] " if entry["is_directory"] else "[FILE]"
            size = "" if entry["is_directory"] else f" ({entry['size']:,} bytes)"
            modified = datetime.fromisoformat(entry["modified"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            result.append(f"{prefix} {entry['name']}{size} - {modified}")

        return "\n".join(result)

    async def move_file(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
        overwrite: bool = False,
    ) -> None:
        """Move or rename a file or directory.

        Args:
            source: Source path
            destination: Destination path
            overwrite: Whether to overwrite destination if it exists

        Raises:
            ValueError: If paths are outside allowed directories
            FileNotFoundError: If source does not exist
            FileExistsError: If destination exists and overwrite is False
        """
        source_path, source_allowed = await self.validator.validate_path(source)
        if not source_allowed:
            raise ValueError(f"Source path outside allowed directories: {source}")

        dest_path, dest_allowed = await self.validator.validate_path(destination)
        if not dest_allowed:
            raise ValueError(
                f"Destination path outside allowed directories: {destination}"
            )

        # Check if source exists
        if not source_path.exists():
            raise FileNotFoundError(f"Source does not exist: {source}")

        # Check if destination exists and we're not overwriting
        if dest_path.exists() and not overwrite:
            raise FileExistsError(f"Destination already exists: {destination}")

        try:
            # Use shutil.move which handles cross-filesystem moves
            await anyio.to_thread.run_sync(shutil.move, source_path, dest_path)
        except (PermissionError, shutil.Error) as e:
            raise ValueError(f"Cannot move file: {e}")

    async def get_file_info(self, path: Union[str, Path]) -> FileInfo:
        """Get detailed information about a file or directory.

        Args:
            path: Path to the file or directory

        Returns:
            FileInfo object with detailed information

        Raises:
            ValueError: If path is outside allowed directories
            FileNotFoundError: If file does not exist
        """
        abs_path, allowed = await self.validator.validate_path(path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {path}")

        if not abs_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        return FileInfo(abs_path)

    async def head_file(
        self, path: Union[str, Path], lines: int = 10, encoding: str = "utf-8"
    ) -> str:
        """Read the first N lines of a text file.

        Args:
            path: Path to the file
            lines: Number of lines to read (default: 10)
            encoding: Text encoding (default: utf-8)

        Returns:
            First N lines of the file

        Raises:
            ValueError: If path is outside allowed directories
            FileNotFoundError: If file does not exist
        """
        abs_path, allowed = await self.validator.validate_path(path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {path}")

        try:
            result = []
            async with await anyio.open_file(abs_path, "r", encoding=encoding) as f:
                for _ in range(lines):
                    try:
                        line = await f.readline()
                        if not line:
                            break
                        result.append(line.rstrip("\n"))
                    except UnicodeDecodeError:
                        raise ValueError(f"Cannot decode file as {encoding}: {path}")

            return "\n".join(result)

        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
        except PermissionError:
            raise ValueError(f"Permission denied: {path}")

    async def tail_file(
        self, path: Union[str, Path], lines: int = 10, encoding: str = "utf-8"
    ) -> str:
        """Read the last N lines of a text file.

        Args:
            path: Path to the file
            lines: Number of lines to read (default: 10)
            encoding: Text encoding (default: utf-8)

        Returns:
            Last N lines of the file

        Raises:
            ValueError: If path is outside allowed directories
            FileNotFoundError: If file does not exist
        """
        abs_path, allowed = await self.validator.validate_path(path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {path}")

        try:
            # We need to read the whole file to get the last N lines
            # This could be optimized for very large files
            data = await anyio.to_thread.run_sync(abs_path.read_text, encoding)
            file_lines = data.splitlines()
            start = max(0, len(file_lines) - lines)
            return "\n".join(file_lines[start:])

        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
        except PermissionError:
            raise ValueError(f"Permission denied: {path}")
        except UnicodeDecodeError:
            raise ValueError(f"Cannot decode file as {encoding}: {path}")

    async def edit_file(
        self,
        path: Union[str, Path],
        edits: List[Dict[str, str]],
        encoding: str = "utf-8",
        dry_run: bool = False,
    ) -> str:
        """Edit a text file by replacing line sequences.

        Args:
            path: Path to the file
            edits: List of {oldText, newText} dictionaries
            encoding: Text encoding (default: utf-8)
            dry_run: If True, return diff but don't modify file

        Returns:
            Git-style diff showing changes

        Raises:
            ValueError: If path is outside allowed directories
            FileNotFoundError: If file does not exist
        """
        abs_path, allowed = await self.validator.validate_path(path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {path}")

        try:
            # Read the file content
            current_content = await anyio.to_thread.run_sync(
                abs_path.read_text, encoding
            )
            new_content = current_content

            # Create a diff-style output
            diff_lines = [f"--- {path}", f"+++ {path}"]

            # Apply each edit
            for edit in edits:
                if "oldText" not in edit or "newText" not in edit:
                    continue

                old_text = edit["oldText"]
                new_text = edit["newText"]

                if old_text in new_content:
                    # Add to diff
                    context = new_content.split(old_text, 1)
                    line_number = context[0].count("\n") + 1
                    old_lines = old_text.count("\n") + 1
                    new_lines = new_text.count("\n") + 1

                    diff_lines.append(
                        f"@@ -{line_number},{old_lines} +{line_number},{new_lines} @@"
                    )
                    for line in old_text.splitlines():
                        diff_lines.append(f"-{line}")
                    for line in new_text.splitlines():
                        diff_lines.append(f"+{line}")

                    # Replace the text
                    new_content = new_content.replace(old_text, new_text, 1)

            # If this is not a dry run, write the changes
            if not dry_run and new_content != current_content:
                await anyio.to_thread.run_sync(
                    abs_path.write_text, new_content, encoding
                )

            if new_content == current_content:
                return "No changes made"

            return "\n".join(diff_lines)

        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
        except PermissionError:
            raise ValueError(f"Permission denied: {path}")
        except UnicodeDecodeError:
            raise ValueError(f"Cannot decode file as {encoding}: {path}")

    async def read_file_lines(
        self,
        path: Union[str, Path],
        offset: int = 0,
        limit: Optional[int] = None,
        encoding: str = "utf-8",
    ) -> Tuple[str, Dict[str, Any]]:
        """Read specific lines from a text file using offset and limit.

        Args:
            path: Path to the file
            offset: Line offset (0-based, starts at first line)
            limit: Maximum number of lines to read (None for all remaining)
            encoding: Text encoding (default: utf-8)

        Returns:
            Tuple of (file content, metadata)

        Raises:
            ValueError: If path is outside allowed directories
            FileNotFoundError: If file does not exist
        """
        abs_path, allowed = await self.validator.validate_path(path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {path}")

        # Parameter validation
        if offset < 0:
            raise ValueError("offset must be non-negative")
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative")

        try:
            # Get file stats for metadata
            stats = await anyio.to_thread.run_sync(partial(abs_path.stat))
            total_size = stats.st_size

            # Count total lines in file - we'll need this for context
            total_lines = 0
            line_positions = []  # Store byte position of each line start

            async with await anyio.open_file(abs_path, "rb") as f:
                pos = 0
                line_positions.append(pos)

                while True:
                    line = await f.readline()
                    if not line:
                        break

                    pos += len(line)
                    total_lines += 1
                    # Always store the position of the start of each line
                    # This ensures we have accurate line positions for all lines
                    line_positions.append(pos)

            # Calculate the effective end offset if limit is specified
            end_offset = None
            if limit is not None:
                end_offset = offset + limit - 1  # Convert limit to inclusive end offset

            # Make sure we don't go beyond the file
            if offset >= total_lines:
                content = ""  # Nothing to read
            else:
                # Adjust end_offset if it exceeds total lines
                if end_offset is None or end_offset >= total_lines:
                    end_offset = total_lines - 1

                # Determine byte positions to read
                start_pos = line_positions[offset]  # Use 0-based offset directly

                # Calculate end position
                if end_offset >= len(line_positions) - 1:
                    # If we're requesting the last line
                    end_pos = total_size
                else:
                    # Normal case - use the position of the line AFTER the end offset
                    end_pos = line_positions[end_offset + 1]

                # Read the content
                async with await anyio.open_file(abs_path, "rb") as f:
                    await f.seek(start_pos)
                    content_bytes = await f.read(end_pos - start_pos)

                    try:
                        content = content_bytes.decode(encoding)
                    except UnicodeDecodeError:
                        raise ValueError(f"Cannot decode file as {encoding}")

            # Calculate the number of lines read
            if offset >= total_lines:
                lines_read = 0
            elif end_offset is None:
                lines_read = total_lines - offset
            else:
                lines_read = min((end_offset - offset + 1), (total_lines - offset))

            # Prepare metadata
            metadata = {
                "path": str(abs_path),
                "offset": offset,
                "limit": limit,
                "end_offset": end_offset,
                "total_lines": total_lines,
                "lines_read": lines_read,
                "total_size": total_size,
                "size_read": len(content),
                "encoding": encoding,
            }

            return content, metadata

        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
        except PermissionError:
            raise ValueError(f"Permission denied: {path}")

    async def edit_file_at_line(
        self,
        path: Union[str, Path],
        line_edits: List[Dict[str, Any]],
        offset: int = 0,
        limit: Optional[int] = None,
        relative_line_numbers: bool = False,
        abort_on_verification_failure: bool = False,
        encoding: str = "utf-8",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
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

        Returns:
            Dict with edit results including verification information

        Raises:
            ValueError: If path is outside allowed directories
            FileNotFoundError: If file does not exist
        """
        abs_path, allowed = await self.validator.validate_path(path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {path}")

        # Parameter validation
        if offset < 0:
            raise ValueError("offset must be non-negative")
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative")

        try:
            # Read the entire file
            content = await anyio.to_thread.run_sync(
                partial(abs_path.read_text, encoding=encoding)
            )
            lines = content.splitlines(keepends=True)

            # Calculate effective range
            end_offset = None
            if limit is not None:
                end_offset = offset + limit - 1
            else:
                end_offset = len(lines) - 1

            # Ensure end_offset is within bounds
            if end_offset >= len(lines):
                end_offset = len(lines) - 1

            # Track verification failures
            verification_failures = []

            # Validate line_edits and adjust line numbers if needed
            for i, edit in enumerate(line_edits):
                if "line_number" not in edit:
                    raise ValueError(f"Edit {i} is missing line_number")
                if "action" not in edit:
                    raise ValueError(f"Edit {i} is missing action")

                line_num = edit["line_number"]
                action = edit["action"]

                # Handle relative line numbers
                absolute_line_num = line_num
                if relative_line_numbers:
                    # If relative, line_num is 0-based and relative to offset
                    if line_num < 0:
                        raise ValueError(
                            f"Relative line number {line_num} must be non-negative"
                        )
                    absolute_line_num = offset + line_num + 1
                else:
                    # Not relative, line_num is 1-based (standard line numbers)
                    absolute_line_num = line_num

                # Store the adjusted line number for later use
                edit["_absolute_line_num"] = absolute_line_num

                # Check if line is within the considered range
                if (
                    absolute_line_num < 1 or absolute_line_num > len(lines) + 1
                ):  # +1 to allow appending at the end
                    raise ValueError(
                        f"Line number {absolute_line_num} is outside file bounds (1-{len(lines)})"
                    )

                if offset > 0 and absolute_line_num < offset + 1:
                    raise ValueError(
                        f"Line number {absolute_line_num} is before offset {offset}"
                    )

                if limit is not None and absolute_line_num > offset + limit:
                    raise ValueError(
                        f"Line number {absolute_line_num} is beyond limit (offset {offset} + limit {limit})"
                    )

                if action not in ["replace", "insert_before", "insert_after", "delete"]:
                    raise ValueError(f"Invalid action '{action}' in edit {i}")

                if action != "delete" and "content" not in edit:
                    raise ValueError(
                        f"Edit {i} with action '{action}' is missing content"
                    )

                # Verify expected content if provided
                if "expected_content" in edit and absolute_line_num <= len(lines):
                    expected = edit["expected_content"]
                    actual = lines[absolute_line_num - 1].rstrip("\r\n")
                    if expected.rstrip("\r\n") != actual:
                        failure = {
                            "edit_index": i,
                            "line": absolute_line_num,
                            "action": action,
                            "expected": expected,
                            "actual": actual,
                        }
                        verification_failures.append(failure)

                        if abort_on_verification_failure:
                            return {
                                "success": False,
                                "path": str(abs_path),
                                "verification_failures": verification_failures,
                                "message": f"Content verification failed at line {absolute_line_num}",
                                "edits_applied": 0,
                                "changes": [],
                                "dry_run": dry_run,
                            }

            # If there are verification failures but we're not aborting,
            # we'll continue with the edits and report the failures

            # Sort edits by absolute line number in reverse order to avoid line number changes
            line_edits = sorted(
                line_edits, key=lambda e: e["_absolute_line_num"], reverse=True
            )

            # Apply edits
            results = []

            for edit in line_edits:
                # Use the adjusted absolute line number
                line_num = edit["_absolute_line_num"]
                action = edit["action"]
                content_before = lines[line_num - 1] if line_num <= len(lines) else ""

                if action == "replace":
                    # Ensure proper line endings
                    new_content = edit["content"]
                    if not new_content.endswith("\n") and content_before.endswith("\n"):
                        new_content += "\n"

                    if line_num <= len(lines):
                        lines[line_num - 1] = new_content
                    else:
                        # If replacing beyond the end, append with any necessary newlines
                        while len(lines) < line_num - 1:
                            lines.append("\n")
                        lines.append(new_content)

                    results.append(
                        {
                            "line": line_num,
                            "original_line_number": edit["line_number"],
                            "action": "replace",
                            "before": content_before,
                            "after": new_content,
                        }
                    )

                elif action == "insert_before":
                    # Ensure proper line endings
                    new_content = edit["content"]
                    if not new_content.endswith("\n"):
                        new_content += "\n"

                    if line_num <= len(lines):
                        lines.insert(line_num - 1, new_content)
                    else:
                        # If inserting beyond the end, append with any necessary newlines
                        while len(lines) < line_num - 1:
                            lines.append("\n")
                        lines.append(new_content)

                    results.append(
                        {
                            "line": line_num,
                            "original_line_number": edit["line_number"],
                            "action": "insert_before",
                            "content": new_content,
                        }
                    )

                elif action == "insert_after":
                    # Ensure proper line endings
                    new_content = edit["content"]
                    if not new_content.endswith("\n"):
                        new_content += "\n"

                    if line_num <= len(lines):
                        lines.insert(line_num, new_content)
                    else:
                        # If inserting beyond the end, append with any necessary newlines
                        while len(lines) < line_num:
                            lines.append("\n")
                        lines.append(new_content)

                    results.append(
                        {
                            "line": line_num,
                            "action": "insert_after",
                            "content": new_content,
                        }
                    )

                elif action == "delete":
                    if line_num <= len(lines):
                        deleted_content = lines.pop(line_num - 1)

                        results.append(
                            {
                                "line": line_num,
                                "action": "delete",
                                "content": deleted_content,
                            }
                        )
                    else:
                        results.append(
                            {
                                "line": line_num,
                                "action": "delete",
                                "error": "Line does not exist",
                            }
                        )

            # Write back the file if not a dry run
            if not dry_run:
                new_content = "".join(lines)
                await anyio.to_thread.run_sync(
                    partial(abs_path.write_text, new_content, encoding=encoding)
                )

            return {
                "path": str(abs_path),
                "edits_applied": len(results),
                "dry_run": dry_run,
                "changes": results,
            }

        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
        except PermissionError:
            raise ValueError(f"Permission denied: {path}")
        except UnicodeDecodeError:
            raise ValueError(f"Cannot decode file as {encoding}")

    async def search_files(
        self,
        root_path: Union[str, Path],
        pattern: str,
        recursive: bool = True,
        exclude_patterns: Optional[List[str]] = None,
        content_match: Optional[str] = None,
        max_results: int = 1000,
        encoding: str = "utf-8",
    ) -> List[Dict]:
        """Search for files matching pattern and/or containing text.

        Args:
            root_path: Starting directory for search
            pattern: Glob pattern to match against filenames
            recursive: Whether to search subdirectories
            exclude_patterns: Optional patterns to exclude
            content_match: Optional text to search within files
            max_results: Maximum number of results to return
            encoding: Text encoding for content matching

        Returns:
            List of matching file information

        Raises:
            ValueError: If root_path is outside allowed directories
        """
        # Find files matching the pattern
        matching_files = await self.validator.find_matching_files(
            root_path, pattern, recursive, exclude_patterns
        )

        results = []

        # If we don't need to match content, just return file info
        if content_match is None:
            for file_path in matching_files[:max_results]:
                try:
                    # Skip directories if pattern matched them
                    if file_path.is_dir():
                        continue

                    info = FileInfo(file_path)
                    results.append(info.to_dict())
                except (PermissionError, FileNotFoundError):
                    # Skip files we can't access
                    pass

            return results

        # If we need to match content, check each file
        for file_path in matching_files:
            if len(results) >= max_results:
                break

            try:
                # Skip directories
                if file_path.is_dir():
                    continue

                # Skip very large files for content matching (>10MB)
                if file_path.stat().st_size > 10_000_000:
                    continue

                # Check if file contains the search text
                try:
                    content = await anyio.to_thread.run_sync(
                        file_path.read_text, encoding
                    )
                    if content_match in content:
                        info = FileInfo(file_path)
                        results.append(info.to_dict())
                except UnicodeDecodeError:
                    # Skip binary files
                    pass

            except (PermissionError, FileNotFoundError):
                # Skip files we can't access
                pass

        return results
