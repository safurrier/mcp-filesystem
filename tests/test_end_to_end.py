"""End-to-end tests for MCP Filesystem server.

These tests verify the system works correctly from client to server,
simulating how it would be used in a real environment.
"""

import json
from pathlib import Path
import tempfile
import shutil

import pytest

from mcp_filesystem.server import (
    mcp,
    read_file,
    write_file,
    list_directory,
    edit_file_at_line,
    grep_files,
    read_file_lines,
    directory_tree
)


class MockLifespanContext:
    """Mock lifespan context for the MCP server."""

    def __init__(self, test_dir):
        from mcp_filesystem.security import PathValidator
        from mcp_filesystem.operations import FileOperations
        from mcp_filesystem.grep import GrepTools
        from mcp_filesystem.advanced import AdvancedFileOperations

        self.validator = PathValidator([str(test_dir)])
        self.operations = FileOperations(self.validator)
        self.grep = GrepTools(self.validator)
        self.advanced = AdvancedFileOperations(self.validator, self.operations)
        self.allowed_dirs = [str(test_dir)]


class MockRequestContext:
    """Mock request context for the MCP server."""

    def __init__(self, lifespan_context):
        self.lifespan_context = lifespan_context


class MockContext:
    """Mock context for MCP server."""

    def __init__(self, test_dir):
        self.lifespan_context = MockLifespanContext(test_dir)
        self.request_context = MockRequestContext(self.lifespan_context)


@pytest.fixture
def test_environment():
    """Create a test environment with files and MCP server."""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp(prefix="mcp_fs_e2e_")
    temp_path = Path(temp_dir)

    # Create test files
    test_file = temp_path / "test.txt"
    test_file.write_text("Line 1\nLine 2\nLine 3\n")

    # Create a subdirectory with a file
    subdir = temp_path / "subdir"
    subdir.mkdir()
    subdir_file = subdir / "subfile.txt"
    subdir_file.write_text("Subdir file content")

    # No need to create a server instance as we'll use the function directly
    # Configure the test environment with allowed directories
    from mcp_filesystem.server import _components_cache
    _components_cache.clear()  # Clear cache to ensure clean test state
    
    # Set environment variable for allowed dirs
    import os
    old_env = os.environ.get("MCP_ALLOWED_DIRS", "")
    os.environ["MCP_ALLOWED_DIRS"] = str(temp_path)

    # Create mock context
    mock_ctx = MockContext(temp_path)

    # Yield the environment for tests to use
    result = {
        "test_dir": temp_path,
        "mock_ctx": mock_ctx,
        "test_file": test_file,
        "subdir_file": subdir_file,
    }

    yield result

    # Clean up
    # Restore environment
    if old_env:
        os.environ["MCP_ALLOWED_DIRS"] = old_env
    else:
        os.environ.pop("MCP_ALLOWED_DIRS", None)
    
    # Clear component cache
    _components_cache.clear()
    
    # Remove temp directory
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
class TestEndToEnd:
    """End-to-end tests for the MCP Filesystem server.

    These tests simulate client interactions with the server.
    """

    async def test_read_file_e2e(self, test_environment):
        """Test reading a file through the server API."""
        # Arrange
        test_file = test_environment["test_file"]
        mock_ctx = test_environment["mock_ctx"]

        # Act
        result = await read_file(str(test_file), mock_ctx)

        # Assert
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    async def test_write_file_e2e(self, test_environment):
        """Test writing a file through the server API."""
        # Arrange
        test_dir = test_environment["test_dir"]
        mock_ctx = test_environment["mock_ctx"]
        new_file_path = test_dir / "new_e2e_file.txt"
        new_content = "Content created in E2E test"

        # Act
        result = await write_file(str(new_file_path), new_content, mock_ctx)

        # Assert
        assert "Successfully" in result
        assert new_file_path.exists()
        assert new_file_path.read_text() == new_content

    async def test_list_directory_e2e(self, test_environment):
        """Test listing a directory through the server API."""
        # Arrange
        test_dir = test_environment["test_dir"]
        mock_ctx = test_environment["mock_ctx"]

        # Act - Use JSON format for consistent parsing
        result = await list_directory(str(test_dir), mock_ctx, format="json")

        # Parse the JSON result
        entries = json.loads(result)

        # Assert
        assert len(entries) >= 2  # At least test.txt and subdir

        # Find files and directories using the actual API fields (is_directory, is_file)
        file_entries = [e for e in entries if e["is_file"] is True]
        dir_entries = [e for e in entries if e["is_directory"] is True]

        assert any(e["name"] == "test.txt" for e in file_entries)
        assert any(e["name"] == "subdir" for e in dir_entries)

    async def test_read_file_lines_e2e(self, test_environment):
        """Test reading specific lines from a file through the server API."""
        # Arrange
        test_file = test_environment["test_file"]
        mock_ctx = test_environment["mock_ctx"]

        # Act - using offset/limit instead of start_line/end_line
        result = await read_file_lines(
            str(test_file),
            mock_ctx,
            offset=1,  # 0-based, corresponds to line 2
            limit=1,
        )

        # Assert
        assert "Line 2" in result
        assert "Line 1" not in result
        assert "Line 3" not in result

    async def test_read_file_lines_out_of_range_e2e(self, test_environment):
        """Test reading out of range lines from a file through the server API."""
        # Arrange
        test_file = test_environment["test_file"]
        mock_ctx = test_environment["mock_ctx"]

        # Act - request beyond file end
        result = await read_file_lines(
            str(test_file),
            mock_ctx,
            offset=10,  # Beyond file end
        )

        # Assert - should get a meaningful message, not an error
        assert "No content found" in result

    async def test_grep_files_e2e(self, test_environment):
        """Test searching files with grep through the server API."""
        # Arrange
        test_dir = test_environment["test_dir"]
        mock_ctx = test_environment["mock_ctx"]

        # First add a file with specific content to search for
        grep_test_file = test_dir / "grep_test.txt"
        grep_test_file.write_text(
            "This file contains the search term we're looking for.\nAnother line without the term."
        )

        # Act
        result = await grep_files(
            str(test_dir), "search term", mock_ctx
        )

        # Assert
        assert "search term" in result
        assert "grep_test.txt" in result
        assert "1 matches" in result or "1 match" in result

    async def test_edit_file_at_line_e2e(self, test_environment):
        """Test editing a specific line in a file through the server API."""
        # Arrange
        test_file = test_environment["test_file"]
        mock_ctx = test_environment["mock_ctx"]

        # Get the current file state
        test_file.read_text()  # Ensure file exists

        # Prepare edit
        line_edits = [
            {"line_number": 2, "action": "replace", "content": "Modified Line 2"}
        ]

        # Act
        result = await edit_file_at_line(
            str(test_file), line_edits, mock_ctx
        )

        # Assert
        assert "Line 2" in result or "line 2" in result.lower()

        # Check file content
        new_content = test_file.read_text()
        assert "Modified Line 2" in new_content
        assert "Line 1" in new_content  # Line 1 should be unchanged
        assert "Line 3" in new_content  # Line 3 should be unchanged

    async def test_edit_file_at_line_with_verification_e2e(self, test_environment):
        """Test editing a file with content verification through the server API."""
        # Arrange
        test_file = test_environment["test_file"]
        mock_ctx = test_environment["mock_ctx"]

        # Reset content to known state
        original_content = "Line 1\nLine 2\nLine 3\n"
        test_file.write_text(original_content)

        # Prepare edit with incorrect expected content
        line_edits = [
            {
                "line_number": 2,
                "action": "replace",
                "content": "Modified Line 2",
                "expected_content": "This is not the actual content",
            }
        ]

        # Act
        result = await edit_file_at_line(
            str(test_file), line_edits, mock_ctx, abort_on_verification_failure=True
        )

        # Assert
        assert "Verification failed" in result or "verification" in result.lower()

        # File content should remain unchanged
        assert test_file.read_text() == original_content

    async def test_edit_file_at_line_with_relative_numbers_e2e(self, test_environment):
        """Test editing a file with relative line numbers through the server API."""
        # Arrange
        test_file = test_environment["test_file"]
        mock_ctx = test_environment["mock_ctx"]

        # Reset content to known state
        original_content = "Line 1\nLine 2\nLine 3\n"
        test_file.write_text(original_content)

        # Prepare edit using relative line numbers
        line_edits = [
            {
                "line_number": 1,  # Relative line number (offset + 1 = line 3)
                "action": "replace",
                "content": "Modified Line 3 Using Relative Numbering",
            }
        ]

        # Act
        result = await edit_file_at_line(
            str(test_file),
            line_edits,
            mock_ctx,
            offset=1,  # Start at line 2
            relative_line_numbers=True,
        )

        # Assert
        assert "Applied" in result

        # File content should have line 3 changed
        new_content = test_file.read_text().splitlines()
        assert new_content[2] == "Modified Line 3 Using Relative Numbering"
        assert new_content[0] == "Line 1"  # Line 1 unchanged
        assert new_content[1] == "Line 2"  # Line 2 unchanged

    async def test_directory_tree_e2e(self, test_environment):
        """Test generating a directory tree through the server API."""
        # Arrange
        test_dir = test_environment["test_dir"]
        mock_ctx = test_environment["mock_ctx"]

        # Act - Use JSON format for consistent parsing
        result = await directory_tree(str(test_dir), mock_ctx, format="json")

        # Parse JSON result
        tree = json.loads(result)

        # Assert
        assert tree["type"] == "directory"
        assert tree["name"] == test_dir.name

        # Check that children exist and have the expected structure
        assert "children" in tree
        assert len(tree["children"]) >= 2  # At least test.txt and subdir

        # Find the subdir in the tree
        subdir = next((c for c in tree["children"] if c["name"] == "subdir"), None)
        assert subdir is not None
        assert subdir["type"] == "directory"
        assert "children" in subdir
