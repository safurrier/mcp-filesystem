"""Enhanced grep functionality for MCP filesystem server.

This module provides powerful grep-like searching capabilities,
with ripgrep integration when available and a Python fallback.
"""

import json
import re
import subprocess
from functools import partial  # Added for mypy compatibility with run_sync
from pathlib import Path
from typing import Dict, List, Optional, Union, Callable, Any

import anyio
from mcp.server.fastmcp.utilities.logging import get_logger

from .security import PathValidator

logger = get_logger(__name__)


class GrepMatch:
    """Represents a single grep match."""

    def __init__(
        self,
        file_path: str,
        line_number: int,
        line_content: str,
        match_start: int,
        match_end: int,
        context_before: Optional[List[str]] = None,
        context_after: Optional[List[str]] = None,
    ):
        """Initialize a grep match.

        Args:
            file_path: Path to the file containing the match
            line_number: Line number of the match (1-based)
            line_content: Content of the matching line
            match_start: Start index of the match within the line
            match_end: End index of the match within the line
            context_before: Lines before the match
            context_after: Lines after the match
        """
        self.file_path = file_path
        self.line_number = line_number
        self.line_content = line_content
        self.match_start = match_start
        self.match_end = match_end
        self.context_before = context_before or []
        self.context_after = context_after or []

    def to_dict(self) -> Dict:
        """Convert to dictionary representation.

        Returns:
            Dictionary with match information
        """
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "line_content": self.line_content,
            "match_start": self.match_start,
            "match_end": self.match_end,
            "context_before": self.context_before,
            "context_after": self.context_after,
        }

    def __str__(self) -> str:
        """Get string representation.

        Returns:
            Formatted string with match information
        """
        return f"{self.file_path}:{self.line_number}: {self.line_content}"


class GrepResult:
    """Result of a grep operation."""

    def __init__(self):
        """Initialize an empty grep result."""
        self.matches: List[GrepMatch] = []
        self.file_counts: Dict[str, int] = {}
        self.total_matches = 0
        self.files_searched = 0
        self.errors: Dict[str, str] = {}

    def add_match(self, match: GrepMatch) -> None:
        """Add a match to the results.

        Args:
            match: GrepMatch to add
        """
        self.matches.append(match)
        self.total_matches += 1

        # Update file counts
        if match.file_path in self.file_counts:
            self.file_counts[match.file_path] += 1
        else:
            self.file_counts[match.file_path] = 1

    def add_file_error(self, file_path: str, error: str) -> None:
        """Add a file error to the results.

        Args:
            file_path: Path to the file with the error
            error: Error message
        """
        self.errors[file_path] = error

    def increment_files_searched(self) -> None:
        """Increment the count of files searched."""
        self.files_searched += 1

    def to_dict(self) -> Dict:
        """Convert to dictionary representation.

        Returns:
            Dictionary with all results
        """
        return {
            "matches": [match.to_dict() for match in self.matches],
            "file_counts": self.file_counts,
            "total_matches": self.total_matches,
            "files_searched": self.files_searched,
            "errors": self.errors,
        }

    def format_text(
        self,
        show_line_numbers: bool = True,
        show_file_names: bool = True,
        count_only: bool = False,
        show_context: bool = True,
        highlight: bool = True,
    ) -> str:
        """Format results as text.

        Args:
            show_line_numbers: Include line numbers in output
            show_file_names: Include file names in output
            count_only: Only show match counts per file
            show_context: Show context lines if available
            highlight: Highlight matches

        Returns:
            Formatted string with results
        """
        if count_only:
            lines = [
                f"Found {self.total_matches} matches in {len(self.file_counts)} files:"
            ]
            for file_path, count in sorted(self.file_counts.items()):
                lines.append(f"{file_path}: {count} matches")
            return "\n".join(lines)

        if not self.matches:
            return "No matches found"

        lines = []
        current_file = None

        for match in self.matches:
            # Add file header if changed
            if show_file_names and match.file_path != current_file:
                current_file = match.file_path
                lines.append(f"\n{current_file}:")

            # Add context before
            if show_context and match.context_before:
                for i, context in enumerate(match.context_before):
                    context_line_num = match.line_number - len(match.context_before) + i
                    if show_line_numbers:
                        lines.append(f"{context_line_num:>6}: {context}")
                    else:
                        lines.append(f"{context}")

            # Add matching line
            line_prefix = ""
            if show_line_numbers:
                line_prefix = f"{match.line_number:>6}: "

            if highlight:
                # Highlight the match in the line
                line = match.line_content
                highlighted = (
                    line[: match.match_start]
                    + ">>>"
                    + line[match.match_start : match.match_end]
                    + "<<<"
                    + line[match.match_end :]
                )
                lines.append(f"{line_prefix}{highlighted}")
            else:
                lines.append(f"{line_prefix}{match.line_content}")

            # Add context after
            if show_context and match.context_after:
                for i, context in enumerate(match.context_after):
                    context_line_num = match.line_number + i + 1
                    if show_line_numbers:
                        lines.append(f"{context_line_num:>6}: {context}")
                    else:
                        lines.append(f"{context}")

        # Add summary
        summary = (
            f"\nFound {self.total_matches} matches in {len(self.file_counts)} files"
        )
        if self.errors:
            summary += f" ({len(self.errors)} files had errors)"
        lines.append(summary)

        return "\n".join(lines)


class GrepTools:
    """Enhanced grep functionality with ripgrep integration."""

    def __init__(self, validator: PathValidator):
        """Initialize with a path validator.

        Args:
            validator: PathValidator for security checks
        """
        self.validator = validator
        self._ripgrep_available = self._check_ripgrep()

    def _check_ripgrep(self) -> bool:
        """Check if ripgrep is available.

        Returns:
            True if ripgrep is available, False otherwise
        """
        try:
            subprocess.run(
                ["rg", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            logger.info("Ripgrep is available")
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.info("Ripgrep not found, using Python fallback")
            return False

    async def grep_files(
        self,
        path: Union[str, Path],
        pattern: str,
        is_regex: bool = False,
        case_sensitive: bool = True,
        whole_word: bool = False,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        context_lines: int = 0,
        context_before: int = 0,
        context_after: int = 0,
        max_results: int = 1000,
        max_file_size_mb: float = 10,
        recursive: bool = True,
        max_depth: Optional[int] = None,
        count_only: bool = False,
        results_offset: int = 0,
        results_limit: Optional[int] = None,
        show_progress: bool = False,
        progress_callback: Optional[Callable[[int, int], Any]] = None,
    ) -> GrepResult:
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
            max_results: Maximum total matches to find during search
            max_file_size_mb: Skip files larger than this size
            recursive: Whether to search subdirectories
            max_depth: Maximum directory depth to recurse
            count_only: Only show match counts per file
            results_offset: Start at Nth match (0-based, for pagination)
            results_limit: Return at most this many matches (for pagination)
            show_progress: Whether to show progress
            progress_callback: Optional callback for progress updates

        Returns:
            GrepResult object with matches and statistics

        Raises:
            ValueError: If path is outside allowed directories
        """
        abs_path, allowed = await self.validator.validate_path(path)
        if not allowed:
            raise ValueError(f"Path outside allowed directories: {path}")

        if self._ripgrep_available and not count_only:
            # Use ripgrep for better performance
            try:
                return await self._grep_with_ripgrep(
                    abs_path,
                    pattern,
                    is_regex,
                    case_sensitive,
                    whole_word,
                    include_patterns,
                    exclude_patterns,
                    context_lines,
                    context_before,
                    context_after,
                    max_results,
                    recursive,
                    max_depth,
                    results_offset,
                    results_limit,
                )
            except Exception as e:
                logger.warning(f"Ripgrep failed, falling back to Python: {e}")

        # Fall back to Python implementation
        return await self._grep_with_python(
            abs_path,
            pattern,
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
            show_progress,
            progress_callback,
            results_offset,
            results_limit,
        )

    async def _grep_with_ripgrep(
        self,
        path: Path,
        pattern: str,
        is_regex: bool,
        case_sensitive: bool,
        whole_word: bool,
        include_patterns: Optional[List[str]],
        exclude_patterns: Optional[List[str]],
        context_lines: int,
        context_before: int,
        context_after: int,
        max_results: int,
        recursive: bool,
        max_depth: Optional[int],
        results_offset: int = 0,
        results_limit: Optional[int] = None,
    ) -> GrepResult:
        """Use ripgrep for searching.

        Args:
            See grep_files for parameter descriptions

        Returns:
            GrepResult with matches

        Raises:
            RuntimeError: If ripgrep fails
        """
        # Build ripgrep command
        cmd = ["rg"]

        # Basic options
        cmd.append("--json")  # JSON output for parsing

        if not is_regex:
            cmd.append("--fixed-strings")

        if not case_sensitive:
            cmd.append("--ignore-case")

        if whole_word:
            cmd.append("--word-regexp")

        # Apply context options (priority: specific before/after over general context)
        if context_before > 0:
            cmd.extend(["--before-context", str(context_before)])

        if context_after > 0:
            cmd.extend(["--after-context", str(context_after)])

        # Only use general context if specific before/after not provided
        elif context_lines > 0 and context_before == 0 and context_after == 0:
            cmd.extend(["--context", str(context_lines)])

        if not recursive:
            cmd.append("--no-recursive")

        if max_depth is not None:
            cmd.extend(["--max-depth", str(max_depth)])

        # Include/exclude patterns
        if include_patterns:
            for pattern_glob in include_patterns:
                cmd.extend(["--glob", pattern_glob])

        if exclude_patterns:
            for pattern_glob in exclude_patterns:
                cmd.extend(["--glob", f"!{pattern_glob}"])

        # Add pattern and path
        cmd.append(pattern)
        cmd.append(str(path))

        # Run ripgrep
        result = GrepResult()

        try:
            process = await anyio.run_process(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Parse JSON output
            output = process.stdout.decode("utf-8", errors="replace")
            error_output = process.stderr.decode("utf-8", errors="replace")

            if (
                process.returncode != 0 and process.returncode != 1
            ):  # 1 means no matches
                raise RuntimeError(f"Ripgrep failed: {error_output}")

            # Process each line (each is a JSON object)
            current_file = None
            current_file_path = None
            line_context: Dict[int, List[str]] = {}  # line_number -> context lines

            for line in output.splitlines():
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)
                    match_type = data.get("type")

                    if match_type == "begin":
                        # New file
                        current_file = data.get("data", {}).get("path", {}).get("text")
                        if current_file:
                            # Validate the file is allowed
                            file_path = Path(current_file)
                            file_abs, file_allowed = await self.validator.validate_path(
                                file_path
                            )
                            if file_allowed:
                                current_file_path = current_file
                            else:
                                current_file_path = None

                    elif match_type == "match" and current_file_path:
                        # Match in current file
                        match_data = data.get("data", {})
                        line_number = match_data.get("line_number", 0)

                        # Extract the submatches
                        submatches = match_data.get("submatches", [])
                        if not submatches:
                            continue

                        line_content = (
                            match_data.get("lines", {}).get("text", "").rstrip("\n")
                        )

                        for submatch in submatches:
                            match_start = submatch.get("start", 0)
                            match_end = (
                                match_start
                                + submatch.get("end", 0)
                                - submatch.get("start", 0)
                            )

                            # Create a match
                            context_before_lines: List[str] = []
                            context_after_lines: List[str] = []

                            # No need to determine line context variables here as we set them directly in the loops below

                            # Get context before from line_context if available
                            before_lines = (
                                context_before if context_before > 0 else context_lines
                            )
                            for i in range(line_number - before_lines, line_number):
                                if i in line_context:
                                    # line_context[i] is a List[str], but we need to add a single string
                                    # to our own list, so we take just the first element or an empty string
                                    ctx_line = (
                                        line_context[i][0] if line_context[i] else ""
                                    )
                                    context_before_lines.append(ctx_line)

                            # We don't actually have context after in the ripgrep output format
                            # in our current implementation

                            match = GrepMatch(
                                file_path=current_file_path,
                                line_number=line_number,
                                line_content=line_content,
                                match_start=match_start,
                                match_end=match_end,
                                context_before=context_before_lines,
                                context_after=context_after_lines,
                            )

                            result.add_match(match)

                            if len(result.matches) >= max_results:
                                return result

                    elif match_type == "context" and current_file_path:
                        # Context line
                        context_data = data.get("data", {})
                        line_number = context_data.get("line_number", 0)
                        line_content = (
                            context_data.get("lines", {}).get("text", "").rstrip("\n")
                        )

                        # Store context line
                        line_context[line_number] = line_content

                        # Check if this is context after a match and update it
                        for match in reversed(result.matches):
                            if (
                                match.file_path == current_file_path
                                and match.line_number < line_number
                            ):
                                if line_number <= match.line_number + context_lines:
                                    match.context_after.append(line_content)
                                break

                    elif match_type == "end" and current_file_path:
                        # End of file
                        current_file = None
                        current_file_path = None
                        line_context.clear()
                        result.increment_files_searched()

                except json.JSONDecodeError:
                    # Skip invalid JSON
                    continue
                except Exception as e:
                    logger.warning(f"Error processing ripgrep output: {e}")

            return result

        except (subprocess.SubprocessError, FileNotFoundError) as e:
            raise RuntimeError(f"Failed to run ripgrep: {e}")

    async def _grep_with_python(
        self,
        path: Path,
        pattern: str,
        is_regex: bool,
        case_sensitive: bool,
        whole_word: bool,
        include_patterns: Optional[List[str]],
        exclude_patterns: Optional[List[str]],
        context_lines: int,
        context_before: int,
        context_after: int,
        max_results: int,
        max_file_size_mb: float,
        recursive: bool,
        max_depth: Optional[int],
        count_only: bool,
        show_progress: bool,
        progress_callback: Optional[Callable[[int, int], Any]],
        results_offset: int = 0,
        results_limit: Optional[int] = None,
    ) -> GrepResult:
        """Use Python implementation for searching.

        Args:
            See grep_files for parameter descriptions

        Returns:
            GrepResult with matches
        """
        result = GrepResult()
        max_file_size = int(max_file_size_mb * 1024 * 1024)

        # Compile regex pattern
        if is_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                if whole_word:
                    compiled_pattern = re.compile(r"\b" + pattern + r"\b", flags)
                else:
                    compiled_pattern = re.compile(pattern, flags)
            except re.error:
                raise ValueError(f"Invalid regex pattern: {pattern}")
        else:
            # For non-regex, use simple string search
            if not case_sensitive:
                pattern = pattern.lower()

            # For whole word, we'll check boundaries during search
            if whole_word:

                def is_whole_word(text: str, start: int, end: int) -> bool:
                    """Check if match is a whole word."""
                    is_start = start == 0 or not text[start - 1].isalnum()
                    is_end = end == len(text) or not text[end].isalnum()
                    return is_start and is_end
            else:

                def is_whole_word(text: str, start: int, end: int) -> bool:
                    """Always return True for non-whole word search."""
                    return True

        # Get file list
        files_to_search: List[Path] = []

        if path.is_file():
            files_to_search.append(path)
        elif recursive:
            # Get all files recursively, respecting max_depth
            async def scan_dir(dir_path: Path, current_depth: int = 0) -> None:
                if max_depth is not None and current_depth > max_depth:
                    return

                try:
                    entries = await anyio.to_thread.run_sync(list, dir_path.iterdir())

                    for entry in entries:
                        try:
                            # Check if path is allowed
                            (
                                entry_abs,
                                entry_allowed,
                            ) = await self.validator.validate_path(entry)
                            if not entry_allowed:
                                continue

                            if entry.is_file():
                                # Apply include/exclude patterns

                                # Skip if doesn't match include patterns
                                if include_patterns:
                                    included = False
                                    for pattern_glob in include_patterns:
                                        if entry.match(pattern_glob):
                                            included = True
                                            break
                                    if not included:
                                        continue

                                # Skip if matches exclude patterns
                                if exclude_patterns:
                                    excluded = False
                                    for pattern_glob in exclude_patterns:
                                        if entry.match(pattern_glob):
                                            excluded = True
                                            break
                                    if excluded:
                                        continue

                                files_to_search.append(entry)

                            elif entry.is_dir():
                                await scan_dir(entry, current_depth + 1)

                        except (PermissionError, FileNotFoundError):
                            # Skip entries we can't access
                            pass

                except (PermissionError, FileNotFoundError):
                    # Skip directories we can't access
                    pass

            await scan_dir(path)

        else:
            # Only get immediate files
            try:
                entries = await anyio.to_thread.run_sync(list, path.iterdir())

                for entry in entries:
                    try:
                        if entry.is_file():
                            # Apply include/exclude patterns
                            if include_patterns:
                                included = False
                                for pattern_glob in include_patterns:
                                    if entry.match(pattern_glob):
                                        included = True
                                        break
                                if not included:
                                    continue

                            if exclude_patterns:
                                excluded = False
                                for pattern_glob in exclude_patterns:
                                    if entry.match(pattern_glob):
                                        excluded = True
                                        break
                                if excluded:
                                    continue

                            files_to_search.append(entry)

                    except (PermissionError, FileNotFoundError):
                        # Skip entries we can't access
                        pass

            except (PermissionError, FileNotFoundError):
                # Skip directories we can't access
                pass

        # Process each file
        total_files = len(files_to_search)

        for i, file_path in enumerate(files_to_search):
            if show_progress and progress_callback:
                await progress_callback(i, total_files)

            try:
                # Skip files that are too large
                file_size = file_path.stat().st_size
                if file_size > max_file_size:
                    result.add_file_error(
                        str(file_path), f"File too large: {file_size} bytes"
                    )
                    continue

                # Read file content
                try:
                    content = await anyio.to_thread.run_sync(
                        partial(file_path.read_text, encoding="utf-8", errors="replace")
                    )
                except UnicodeDecodeError:
                    result.add_file_error(str(file_path), "Binary file")
                    continue

                # Split into lines and preserve line endings
                lines_with_endings = []
                start = 0
                for i, c in enumerate(content):
                    if c == "\n":
                        lines_with_endings.append(content[start : i + 1])
                        start = i + 1

                if start < len(content):
                    lines_with_endings.append(content[start:])

                # Strip line endings for matching
                lines = [line.rstrip("\n\r") for line in lines_with_endings]

                # Search for pattern in each line
                file_matches = 0

                for line_number, line in enumerate(lines, 1):
                    # Skip binary files (lines with null bytes)
                    if "\0" in line:
                        result.add_file_error(str(file_path), "Binary file")
                        break

                    if is_regex:
                        # Use regex search
                        for match in compiled_pattern.finditer(line):
                            match_start, match_end = match.span()

                            # Skip if count only
                            if count_only:
                                file_matches += 1
                                continue

                            # Get context lines
                            context_before_lines: List[str] = []
                            context_after_lines: List[str] = []

                            # Determine how many lines to show before/after
                            before_lines = (
                                context_before if context_before > 0 else context_lines
                            )
                            after_lines = (
                                context_after if context_after > 0 else context_lines
                            )

                            # Get context before match
                            for ctx_line_num in range(
                                max(1, line_number - before_lines), line_number
                            ):
                                context_before_lines.append(lines[ctx_line_num - 1])

                            # Get context after match
                            for ctx_line_num in range(
                                line_number + 1,
                                min(len(lines) + 1, line_number + after_lines + 1),
                            ):
                                context_after_lines.append(lines[ctx_line_num - 1])

                            match_obj = GrepMatch(
                                file_path=str(file_path),
                                line_number=line_number,
                                line_content=line,
                                match_start=match_start,
                                match_end=match_end,
                                context_before=context_before_lines,
                                context_after=context_after_lines,
                            )

                            result.add_match(match_obj)

                            if result.total_matches >= max_results:
                                break
                    else:
                        # Use string search
                        search_line = line.lower() if not case_sensitive else line
                        search_pattern = (
                            pattern.lower() if not case_sensitive else pattern
                        )

                        start_pos = 0
                        while start_pos <= len(search_line) - len(search_pattern):
                            match_pos = search_line.find(search_pattern, start_pos)
                            if match_pos == -1:
                                break

                            match_end = match_pos + len(search_pattern)

                            # Check if it's a whole word
                            if not whole_word or is_whole_word(
                                search_line, match_pos, match_end
                            ):
                                # Skip if count only
                                if count_only:
                                    file_matches += 1
                                else:
                                    # Get context lines
                                    context_before_lines = []
                                    context_after_lines = []

                                    # Determine how many lines to show before
                                    before_lines = (
                                        context_before
                                        if context_before > 0
                                        else context_lines
                                    )

                                    # Determine how many lines to show after
                                    after_lines = (
                                        context_after
                                        if context_after > 0
                                        else context_lines
                                    )

                                    # Get context before the match
                                    for ctx_line_num in range(
                                        max(1, line_number - before_lines), line_number
                                    ):
                                        context_before_lines.append(
                                            lines[ctx_line_num - 1]
                                        )

                                    # Get context after the match
                                    for ctx_line_num in range(
                                        line_number + 1,
                                        min(
                                            len(lines) + 1,
                                            line_number + after_lines + 1,
                                        ),
                                    ):
                                        context_after_lines.append(
                                            lines[ctx_line_num - 1]
                                        )

                                    match_obj = GrepMatch(
                                        file_path=str(file_path),
                                        line_number=line_number,
                                        line_content=line,
                                        match_start=match_pos,
                                        match_end=match_end,
                                        context_before=context_before_lines,
                                        context_after=context_after_lines,
                                    )

                                    result.add_match(match_obj)

                                    if result.total_matches >= max_results:
                                        break

                            start_pos = match_end

                    if result.total_matches >= max_results:
                        break

                # Update file counts for count-only mode
                if count_only and file_matches > 0:
                    result.file_counts[str(file_path)] = file_matches
                    result.total_matches += file_matches

                result.increment_files_searched()

                if result.total_matches >= max_results:
                    break

            except (PermissionError, FileNotFoundError) as e:
                result.add_file_error(str(file_path), str(e))
                continue
            except Exception as e:
                result.add_file_error(str(file_path), f"Error: {str(e)}")
                continue

        if show_progress and progress_callback:
            await progress_callback(total_files, total_files)

        # Apply results pagination if requested
        if results_offset > 0 or results_limit is not None:
            # Create a new result with the same metadata
            paginated_result = GrepResult()
            paginated_result.files_searched = result.files_searched
            paginated_result.total_matches = (
                result.total_matches
            )  # Keep the true total for metadata
            paginated_result.file_counts = result.file_counts.copy()
            paginated_result.errors = result.errors.copy()

            # Calculate the effective range
            start_idx = min(results_offset, len(result.matches))

            if results_limit is not None:
                end_idx = min(start_idx + results_limit, len(result.matches))
            else:
                end_idx = len(result.matches)

            # Copy only the matches in the requested range
            paginated_result.matches = result.matches[start_idx:end_idx]

            # Return the paginated result
            return paginated_result

        return result
