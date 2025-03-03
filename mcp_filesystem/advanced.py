"""Advanced file operations for MCP filesystem server.

This module provides enhanced file operations such as directory tree visualization,
file watching, and batch processing capabilities.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import anyio
from mcp.server.fastmcp.utilities.logging import get_logger

from .operations import FileInfo, FileOperations
from .security import PathValidator

logger = get_logger(__name__)


class DirectoryTreeNode:
    """Node in a directory tree."""

    def __init__(self, path: Path, is_dir: bool = False, depth: int = 0):
        """Initialize a tree node.

        Args:
            path: Path this node represents
            is_dir: Whether this is a directory
            depth: Depth in the tree (0 = root)
        """
        self.path = path
        self.name = path.name or str(path)  # Use path string for root
        self.is_dir = is_dir
        self.depth = depth
        self.children: List["DirectoryTreeNode"] = []

    def add_child(self, child: "DirectoryTreeNode") -> None:
        """Add a child node.

        Args:
            child: Child node to add
        """
        self.children.append(child)

    def to_dict(self) -> Dict:
        """Convert to dictionary representation.

        Returns:
            Dictionary representing this node and its children
        """
        result: Dict[str, Union[str, List[Dict[str, Any]]]] = {
            "name": self.name,
            "path": str(self.path),
            "type": "directory" if self.is_dir else "file",
        }

        if self.is_dir:
            result["children"] = [child.to_dict() for child in self.children]

        return result

    def format(self, include_files: bool = True, line_prefix: str = "") -> List[str]:
        """Format this node as text lines.

        Args:
            include_files: Whether to include files (not just directories)
            line_prefix: Prefix for each line (used for recursion)

        Returns:
            List of formatted lines
        """
        result: List[str] = []

        # Skip files if not requested
        if not include_files and not self.is_dir:
            return result

        # Format this node
        node_type = "📁" if self.is_dir else "📄"
        result.append(f"{line_prefix}{node_type} {self.name}")

        # Format children
        if self.children:
            for i, child in enumerate(
                sorted(self.children, key=lambda x: (not x.is_dir, x.name))
            ):
                is_last = i == len(self.children) - 1
                if is_last:
                    child_prefix = f"{line_prefix}└── "
                    next_prefix = f"{line_prefix}    "
                else:
                    child_prefix = f"{line_prefix}├── "
                    next_prefix = f"{line_prefix}│   "

                result.extend(child.format(include_files, child_prefix + next_prefix))

        return result


class AdvancedFileOperations:
    """Advanced file operations with enhanced capabilities."""

    def __init__(self, validator: PathValidator, base_ops: FileOperations):
        """Initialize with a path validator and base operations.

        Args:
            validator: PathValidator for security checks
            base_ops: Basic FileOperations to build upon
        """
        self.validator = validator
        self.base_ops = base_ops

    async def directory_tree(
        self,
        root_path: Union[str, Path],
        max_depth: int = 3,
        include_files: bool = True,
        pattern: Optional[str] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> Dict:
        """Build a directory tree structure.

        Args:
            root_path: Root directory for the tree
            max_depth: Maximum depth to traverse
            include_files: Whether to include files (not just directories)
            pattern: Optional glob pattern to filter entries
            exclude_patterns: Optional patterns to exclude

        Returns:
            Dictionary representation of the directory tree

        Raises:
            ValueError: If root_path is outside allowed directories
        """
        abs_path, allowed = await self.validator.validate_path(root_path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {root_path}")

        if not abs_path.is_dir():
            raise ValueError(f"Not a directory: {root_path}")

        # Compile exclude patterns if provided
        exclude_regexes = []
        if exclude_patterns:
            for exclude in exclude_patterns:
                try:
                    exclude_regexes.append(re.compile(exclude))
                except re.error:
                    logger.warning(f"Invalid exclude pattern: {exclude}")

        # Create root node
        root_node = DirectoryTreeNode(abs_path, True, 0)

        # Build tree recursively
        await self._build_tree_node(
            root_node, max_depth, include_files, pattern, exclude_regexes
        )

        return root_node.to_dict()

    async def directory_tree_formatted(
        self,
        root_path: Union[str, Path],
        max_depth: int = 3,
        include_files: bool = True,
        pattern: Optional[str] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> str:
        """Build a formatted directory tree.

        Args:
            root_path: Root directory for the tree
            max_depth: Maximum depth to traverse
            include_files: Whether to include files (not just directories)
            pattern: Optional glob pattern to filter entries
            exclude_patterns: Optional patterns to exclude

        Returns:
            Formatted string representation of the directory tree
        """
        abs_path, allowed = await self.validator.validate_path(root_path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {root_path}")

        if not abs_path.is_dir():
            raise ValueError(f"Not a directory: {root_path}")

        # Compile exclude patterns if provided
        exclude_regexes = []
        if exclude_patterns:
            for exclude in exclude_patterns:
                try:
                    exclude_regexes.append(re.compile(exclude))
                except re.error:
                    logger.warning(f"Invalid exclude pattern: {exclude}")

        # Create root node
        root_node = DirectoryTreeNode(abs_path, True, 0)

        # Build tree recursively
        await self._build_tree_node(
            root_node, max_depth, include_files, pattern, exclude_regexes
        )

        # Format the tree
        formatted = root_node.format(include_files)
        return "\n".join(formatted)

    async def _build_tree_node(
        self,
        node: DirectoryTreeNode,
        max_depth: int,
        include_files: bool,
        pattern: Optional[str],
        exclude_regexes: List[re.Pattern],
    ) -> None:
        """Recursively build a directory tree node.

        Args:
            node: Current node to populate
            max_depth: Maximum depth to traverse
            include_files: Whether to include files
            pattern: Optional glob pattern to filter entries
            exclude_regexes: Compiled regular expressions to exclude
        """
        # Stop if we've reached the maximum depth
        if node.depth >= max_depth:
            return

        try:
            entries = await anyio.to_thread.run_sync(list, node.path.iterdir())

            for entry in entries:
                # Skip if matched by exclude pattern
                path_str = str(entry)
                excluded = False
                for exclude_re in exclude_regexes:
                    if exclude_re.search(path_str):
                        excluded = True
                        break

                if excluded:
                    continue

                # Apply pattern filter if specified
                if pattern and not entry.match(pattern):
                    continue

                try:
                    is_dir = entry.is_dir()

                    # Skip files if not requested
                    if not include_files and not is_dir:
                        continue

                    # Create and add the child node
                    child = DirectoryTreeNode(entry, is_dir, node.depth + 1)
                    node.add_child(child)

                    # Recursively build the tree for directories
                    if is_dir:
                        await self._build_tree_node(
                            child, max_depth, include_files, pattern, exclude_regexes
                        )

                except (PermissionError, FileNotFoundError):
                    # Skip entries we can't access
                    pass

        except (PermissionError, FileNotFoundError):
            # Skip directories we can't access
            pass

    async def batch_process_files(
        self,
        paths: List[Union[str, Path]],
        operation: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Union[str, Dict[str, Any], Exception]]:
        """Process multiple files with the same operation.

        Args:
            paths: List of file paths to process
            operation: Operation to perform (read, write, info, etc.)
            parameters: Additional parameters for the operation

        Returns:
            Dictionary mapping file paths to operation results or exceptions
        """
        if parameters is None:
            parameters = {}

        results: Dict[str, Union[str, Dict[str, Any], Exception]] = {}

        for path in paths:
            try:
                str_path = str(path)

                if operation == "read":
                    encoding = parameters.get("encoding", "utf-8")
                    results[str_path] = await self.base_ops.read_file(path, encoding)

                elif operation == "info":
                    info = await self.base_ops.get_file_info(path)
                    results[str_path] = info.to_dict()

                elif operation == "head":
                    lines = parameters.get("lines", 10)
                    encoding = parameters.get("encoding", "utf-8")
                    results[str_path] = await self.base_ops.head_file(
                        path, lines, encoding
                    )

                elif operation == "tail":
                    lines = parameters.get("lines", 10)
                    encoding = parameters.get("encoding", "utf-8")
                    results[str_path] = await self.base_ops.tail_file(
                        path, lines, encoding
                    )

                else:
                    results[str_path] = ValueError(f"Unknown operation: {operation}")

            except Exception as e:
                results[str(path)] = e

        return results

    async def calculate_directory_size(self, path: Union[str, Path]) -> int:
        """Calculate the total size of a directory recursively.

        Args:
            path: Directory path

        Returns:
            Total size in bytes

        Raises:
            ValueError: If path is outside allowed directories
        """
        abs_path, allowed = await self.validator.validate_path(path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {path}")

        if not abs_path.is_dir():
            raise ValueError(f"Not a directory: {path}")

        total_size = 0

        async def scan_dir(dir_path: Path) -> None:
            nonlocal total_size

            try:
                entries = await anyio.to_thread.run_sync(list, dir_path.iterdir())

                for entry in entries:
                    try:
                        if entry.is_file():
                            total_size += entry.stat().st_size
                        elif entry.is_dir():
                            # Check if this path is still allowed
                            (
                                entry_abs,
                                entry_allowed,
                            ) = await self.validator.validate_path(entry)
                            if entry_allowed:
                                await scan_dir(entry)

                    except (PermissionError, FileNotFoundError):
                        # Skip entries we can't access
                        pass

            except (PermissionError, FileNotFoundError):
                # Skip directories we can't access
                pass

        await scan_dir(abs_path)
        return total_size

    async def find_duplicate_files(
        self,
        root_path: Union[str, Path],
        recursive: bool = True,
        min_size: int = 1,
        exclude_patterns: Optional[List[str]] = None,
        max_files: int = 1000,
    ) -> Dict[str, List[str]]:
        """Find duplicate files by comparing file sizes and contents.

        Args:
            root_path: Starting directory
            recursive: Whether to search subdirectories
            min_size: Minimum file size to consider (bytes)
            exclude_patterns: Optional patterns to exclude
            max_files: Maximum number of files to scan

        Returns:
            Dictionary mapping file hash to list of identical files

        Raises:
            ValueError: If root_path is outside allowed directories
        """
        import hashlib

        abs_path, allowed = await self.validator.validate_path(root_path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {root_path}")

        if not abs_path.is_dir():
            raise ValueError(f"Not a directory: {root_path}")

        # Compile exclude patterns if provided
        exclude_regexes = []
        if exclude_patterns:
            for exclude in exclude_patterns:
                try:
                    exclude_regexes.append(re.compile(exclude))
                except re.error:
                    logger.warning(f"Invalid exclude pattern: {exclude}")

        # First, group files by size
        size_groups: Dict[int, List[Path]] = {}
        files_processed = 0

        async def scan_for_sizes(dir_path: Path) -> None:
            nonlocal files_processed

            if files_processed >= max_files:
                return

            try:
                entries = await anyio.to_thread.run_sync(list, dir_path.iterdir())

                for entry in entries:
                    if files_processed >= max_files:
                        return

                    # Skip if matched by exclude pattern
                    path_str = str(entry)
                    excluded = False
                    for exclude_re in exclude_regexes:
                        if exclude_re.search(path_str):
                            excluded = True
                            break

                    if excluded:
                        continue

                    try:
                        if entry.is_file():
                            size = entry.stat().st_size
                            if size >= min_size:
                                if size not in size_groups:
                                    size_groups[size] = []
                                size_groups[size].append(entry)
                                files_processed += 1

                        elif entry.is_dir() and recursive:
                            # Check if this path is still allowed
                            (
                                entry_abs,
                                entry_allowed,
                            ) = await self.validator.validate_path(entry)
                            if entry_allowed:
                                await scan_for_sizes(entry)

                    except (PermissionError, FileNotFoundError):
                        # Skip entries we can't access
                        pass

            except (PermissionError, FileNotFoundError):
                # Skip directories we can't access
                pass

        await scan_for_sizes(abs_path)

        # Now, for each size group with multiple files, compute and compare hashes
        duplicates: Dict[str, List[str]] = {}

        for size, files in size_groups.items():
            if len(files) < 2:
                continue

            # Group files by hash
            hash_groups: Dict[str, List[Path]] = {}

            for file_path in files:
                try:
                    # Compute file hash
                    file_bytes = await anyio.to_thread.run_sync(file_path.read_bytes)
                    file_hash = hashlib.md5(file_bytes).hexdigest()

                    if file_hash not in hash_groups:
                        hash_groups[file_hash] = []
                    hash_groups[file_hash].append(file_path)

                except (PermissionError, FileNotFoundError):
                    # Skip files we can't access
                    pass

            # Add duplicate groups to results
            for file_hash, hash_files in hash_groups.items():
                if len(hash_files) >= 2:
                    duplicates[file_hash] = [str(f) for f in hash_files]

        return duplicates

    async def compare_files(
        self, file1: Union[str, Path], file2: Union[str, Path], encoding: str = "utf-8"
    ) -> Dict:
        """Compare two text files and show differences.

        Args:
            file1: First file path
            file2: Second file path
            encoding: Text encoding (default: utf-8)

        Returns:
            Dictionary with comparison results

        Raises:
            ValueError: If paths are outside allowed directories
        """
        import difflib

        path1, allowed1 = await self.validator.validate_path(file1)
        if not allowed1:
            raise ValueError(f"Path outside allowed directories: {file1}")

        path2, allowed2 = await self.validator.validate_path(file2)
        if not allowed2:
            raise ValueError(f"Path outside allowed directories: {file2}")

        try:
            content1 = await anyio.to_thread.run_sync(path1.read_text, encoding)
            content2 = await anyio.to_thread.run_sync(path2.read_text, encoding)

            # Get file names for display
            name1 = path1.name
            name2 = path2.name

            # Split into lines
            lines1 = content1.splitlines()
            lines2 = content2.splitlines()

            # Calculate differences
            diff = list(
                difflib.unified_diff(
                    lines1, lines2, fromfile=name1, tofile=name2, lineterm=""
                )
            )

            # Count added, removed, and changed lines
            added = sum(
                1
                for line in diff
                if line.startswith("+") and not line.startswith("+++")
            )
            removed = sum(
                1
                for line in diff
                if line.startswith("-") and not line.startswith("---")
            )

            # Calculate similarity ratio
            matcher = difflib.SequenceMatcher(None, content1, content2)
            similarity = matcher.ratio()

            return {
                "diff": "\n".join(diff),
                "added_lines": added,
                "removed_lines": removed,
                "similarity": similarity,
                "are_identical": content1 == content2,
            }

        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {e}")
        except PermissionError as e:
            raise ValueError(f"Permission denied: {e}")
        except UnicodeDecodeError as e:
            raise ValueError(f"Cannot decode file as {encoding}: {e}")

    async def find_large_files(
        self,
        root_path: Union[str, Path],
        min_size_mb: float = 100,
        recursive: bool = True,
        max_results: int = 100,
        exclude_patterns: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Find files larger than the specified size.

        Args:
            root_path: Starting directory
            min_size_mb: Minimum file size in megabytes
            recursive: Whether to search subdirectories
            max_results: Maximum number of results to return
            exclude_patterns: Optional patterns to exclude

        Returns:
            List of file information dictionaries for large files

        Raises:
            ValueError: If root_path is outside allowed directories
        """
        min_size_bytes = int(min_size_mb * 1024 * 1024)

        abs_path, allowed = await self.validator.validate_path(root_path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {root_path}")

        if not abs_path.is_dir():
            raise ValueError(f"Not a directory: {root_path}")

        # Compile exclude patterns if provided
        exclude_regexes = []
        if exclude_patterns:
            for exclude in exclude_patterns:
                try:
                    exclude_regexes.append(re.compile(exclude))
                except re.error:
                    logger.warning(f"Invalid exclude pattern: {exclude}")

        # Find large files
        results: List[Dict[str, Any]] = []

        async def scan_for_large_files(dir_path: Path) -> None:
            if len(results) >= max_results:
                return

            try:
                entries = await anyio.to_thread.run_sync(list, dir_path.iterdir())

                for entry in entries:
                    if len(results) >= max_results:
                        return

                    # Skip if matched by exclude pattern
                    path_str = str(entry)
                    excluded = False
                    for exclude_re in exclude_regexes:
                        if exclude_re.search(path_str):
                            excluded = True
                            break

                    if excluded:
                        continue

                    try:
                        if entry.is_file():
                            size = entry.stat().st_size
                            if size >= min_size_bytes:
                                info = FileInfo(entry)
                                results.append(info.to_dict())

                        elif entry.is_dir() and recursive:
                            # Check if this path is still allowed
                            (
                                entry_abs,
                                entry_allowed,
                            ) = await self.validator.validate_path(entry)
                            if entry_allowed:
                                await scan_for_large_files(entry)

                    except (PermissionError, FileNotFoundError):
                        # Skip entries we can't access
                        pass

            except (PermissionError, FileNotFoundError):
                # Skip directories we can't access
                pass

        await scan_for_large_files(abs_path)

        # Sort by size (largest first)
        return sorted(results, key=lambda x: x["size"], reverse=True)

    async def find_empty_directories(
        self,
        root_path: Union[str, Path],
        recursive: bool = True,
        exclude_patterns: Optional[List[str]] = None,
    ) -> List[str]:
        """Find empty directories.

        Args:
            root_path: Starting directory
            recursive: Whether to search subdirectories
            exclude_patterns: Optional patterns to exclude

        Returns:
            List of empty directory paths

        Raises:
            ValueError: If root_path is outside allowed directories
        """
        abs_path, allowed = await self.validator.validate_path(root_path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {root_path}")

        if not abs_path.is_dir():
            raise ValueError(f"Not a directory: {root_path}")

        # Compile exclude patterns if provided
        exclude_regexes = []
        if exclude_patterns:
            for exclude in exclude_patterns:
                try:
                    exclude_regexes.append(re.compile(exclude))
                except re.error:
                    logger.warning(f"Invalid exclude pattern: {exclude}")

        empty_dirs = []

        async def scan_for_empty_dirs(dir_path: Path) -> bool:
            """Scan for empty directories, return True if directory is empty."""
            try:
                entries = await anyio.to_thread.run_sync(list, dir_path.iterdir())

                if not entries:
                    # Found an empty directory
                    empty_dirs.append(str(dir_path))
                    return True

                # If not recursive, just check if this directory is empty
                if not recursive:
                    return False

                # Check if directory is empty after checking all subdirectories
                is_empty = True

                for entry in entries:
                    # Skip if matched by exclude pattern
                    path_str = str(entry)
                    excluded = False
                    for exclude_re in exclude_regexes:
                        if exclude_re.search(path_str):
                            excluded = True
                            break

                    if excluded:
                        # Treat excluded entries as if they don't exist
                        continue

                    if entry.is_file():
                        # Files make the directory non-empty
                        is_empty = False
                    elif entry.is_dir():
                        # Check if this subdir is allowed
                        entry_abs, entry_allowed = await self.validator.validate_path(
                            entry
                        )
                        if entry_allowed:
                            # If any subdirectory is non-empty, this directory is non-empty
                            subdir_empty = await scan_for_empty_dirs(entry)
                            if not subdir_empty:
                                is_empty = False

                if is_empty:
                    empty_dirs.append(str(dir_path))

                return is_empty

            except (PermissionError, FileNotFoundError):
                # Skip directories we can't access
                return False

        await scan_for_empty_dirs(abs_path)
        return empty_dirs
