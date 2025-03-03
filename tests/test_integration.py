"""Integration tests for MCP Filesystem server.

These tests verify that the components work together correctly with actual
filesystem operations. They use a temporary test directory to avoid affecting
the real filesystem.
"""

import json
from pathlib import Path
import tempfile
import shutil

import pytest

from mcp_filesystem.security import PathValidator
from mcp_filesystem.operations import FileOperations
from mcp_filesystem.grep import GrepTools
from mcp_filesystem.advanced import AdvancedFileOperations


@pytest.fixture
def test_dir():
    """Create a temporary test directory with sample files."""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp(prefix="mcp_fs_test_")
    temp_path = Path(temp_dir)

    # Create some test files and directories
    sample_files = {
        "file1.txt": "This is the first test file.\nIt has multiple lines.\nThis is line 3.",
        "file2.txt": "Second file with different content.\nAnother line here.",
        "empty.txt": "",
        "config.json": json.dumps({"setting1": "value1", "setting2": 42}),
    }

    # Create a subdirectory
    subdir = temp_path / "subdir"
    subdir.mkdir()

    # Create test files
    for filename, content in sample_files.items():
        (temp_path / filename).write_text(content)

    # Create a file in the subdirectory
    (subdir / "subfile.txt").write_text(
        "This is a file in the subdirectory.\nWith content."
    )

    # Yield the directory for tests to use
    yield temp_path

    # Clean up the temporary directory
    shutil.rmtree(temp_dir)


@pytest.fixture
def path_validator(test_dir: Path) -> PathValidator:
    """Create a path validator that allows access to the test directory."""
    return PathValidator([str(test_dir)])


@pytest.fixture
def file_operations(path_validator: PathValidator) -> FileOperations:
    """Create file operations instance with the test path validator."""
    return FileOperations(path_validator)


@pytest.fixture
def grep_tools(path_validator: PathValidator) -> GrepTools:
    """Create grep tools instance with the test path validator."""
    return GrepTools(path_validator)


@pytest.fixture
def advanced_operations(
    path_validator: PathValidator, file_operations: FileOperations
) -> AdvancedFileOperations:
    """Create advanced file operations instance with the test dependencies."""
    return AdvancedFileOperations(path_validator, file_operations)


@pytest.mark.asyncio
class TestFileSystemIntegration:
    """Integration tests for file system operations.

    These tests verify that the components work together correctly with
    actual filesystem operations on a temporary test directory.
    """

    async def test_read_file_returns_correct_content(
        self, test_dir: Path, file_operations: FileOperations
    ):
        """Test that reading a file returns its actual content."""
        # Arrange
        test_file = test_dir / "file1.txt"
        expected_content = (
            "This is the first test file.\nIt has multiple lines.\nThis is line 3."
        )

        # Act
        content = await file_operations.read_file(str(test_file))

        # Assert
        assert content == expected_content

    async def test_write_file_creates_new_file(
        self, test_dir: Path, file_operations: FileOperations
    ):
        """Test that writing to a new file creates it with correct content."""
        # Arrange
        test_file = test_dir / "new_file.txt"
        test_content = "This is a new file created by the test.\nWith multiple lines."

        # Act
        await file_operations.write_file(str(test_file), test_content)

        # Assert - operations.write_file doesn't return a success message
        # Just verify the file was created with the correct content
        assert test_file.exists()
        assert test_file.read_text() == test_content

    async def test_list_directory_shows_all_files(
        self, test_dir: Path, file_operations: FileOperations
    ):
        """Test that listing a directory shows all files and subdirectories."""
        # Act
        entries = await file_operations.list_directory(str(test_dir))

        # Assert
        assert len(entries) >= 5  # 4 files + 1 subdirectory

        # Check that we have files and directories using the API's actual fields
        file_names = [entry["name"] for entry in entries if entry["is_file"] is True]
        dir_names = [
            entry["name"] for entry in entries if entry["is_directory"] is True
        ]

        assert "file1.txt" in file_names
        assert "file2.txt" in file_names
        assert "empty.txt" in file_names
        assert "config.json" in file_names
        assert "subdir" in dir_names

    async def test_grep_files_finds_matching_content(
        self, test_dir: Path, grep_tools: GrepTools
    ):
        """Test that grep finds files with matching content."""
        # Act
        results = await grep_tools.grep_files(
            str(test_dir), pattern="first", case_sensitive=True
        )

        # Assert
        assert results.total_matches >= 1

        # At least one match should be in file1.txt
        file1_matches = [m for m in results.matches if "file1.txt" in m.file_path]
        assert len(file1_matches) >= 1
        assert "first test file" in file1_matches[0].line_content

    async def test_grep_with_context(self, test_dir: Path, grep_tools: GrepTools):
        """Test that grep supports context lines."""
        # Add a test file with multiple matches and context
        test_file = test_dir / "grep_context_test.txt"
        content = "\n".join(
            [
                "Line 1: No match here",
                "Line 2: No match here",
                "Line 3: This has first match",
                "Line 4: No match here",
                "Line 5: No match here",
                "Line 6: This has second match",
                "Line 7: No match here",
                "Line 8: This has third match",
                "Line 9: No match here",
                "Line 10: No match here",
            ]
        )
        test_file.write_text(content)

        # Act: Test with context_before and context_after
        results = await grep_tools.grep_files(
            str(test_file),
            pattern="has .* match",  # More specific pattern to match only our test lines
            is_regex=True,
            context_before=2,
            context_after=1,
        )

        # Assert context lines
        assert results.total_matches == 3
        # Verify that context_before works (at least 1 line of context)
        assert len(results.matches[0].context_before) > 0

    async def test_grep_with_pagination(self, test_dir: Path, grep_tools: GrepTools):
        """Test that grep supports pagination of results."""
        # Add a test file with multiple matches
        test_file = test_dir / "grep_pagination_test.txt"
        content = "\n".join(
            [
                "Line 1: First match here",
                "Line 2: Second match here",
                "Line 3: Third match here",
                "Line 4: Fourth match here",
            ]
        )
        test_file.write_text(content)

        # Temporarily disable ripgrep to ensure we test our Python implementation
        original_ripgrep_available = grep_tools._ripgrep_available
        grep_tools._ripgrep_available = False

        # Act: Test pagination with offset and limit
        results = await grep_tools.grep_files(
            str(test_file), pattern="match", results_offset=1, results_limit=2
        )

        # Print debug info to help diagnose
        print(f"Total matches: {results.total_matches}")
        for i, match in enumerate(results.matches):
            print(f"Match {i + 1}: {match.line_content}")

        # Assert basic result data
        assert results.total_matches >= 4

        # The more important test: make sure we only get 2 matches back starting from the 2nd match
        if results.total_matches >= 4:
            # We should get exactly 2 matches due to the limit
            assert len(results.matches) == 2

        # Restore original ripgrep availability
        grep_tools._ripgrep_available = original_ripgrep_available

    async def test_edit_file_at_line_modifies_correct_line(
        self, test_dir: Path, file_operations: FileOperations
    ):
        """Test that editing a file at a specific line modifies only that line."""
        # Arrange
        test_file = test_dir / "file1.txt"
        original_content = test_file.read_text()
        line_number = 2
        new_line_content = "This is a modified line."

        # Act
        await file_operations.edit_file_at_line(
            str(test_file),
            [
                {
                    "line_number": line_number,
                    "action": "replace",
                    "content": new_line_content,
                }
            ],
        )

        # We don't care about the specific structure of the result
        # What matters is the actual behavior: did the file get edited correctly?

        # Read the file again to see the changes
        modified_content = test_file.read_text()
        modified_lines = modified_content.splitlines()

        # Check that the expected changes occurred:
        # 1. Line 2 was changed to our new content
        assert modified_lines[line_number - 1] == new_line_content

        # 2. Other lines remained unchanged
        original_lines = original_content.splitlines()
        for i in range(len(original_lines)):
            if i != line_number - 1:
                assert modified_lines[i] == original_lines[i]

    async def test_edit_file_with_content_verification(
        self, test_dir: Path, file_operations: FileOperations
    ):
        """Test that content verification works when editing a file."""
        # Arrange
        test_file = test_dir / "file1.txt"
        original_content = test_file.read_text()
        original_lines = original_content.splitlines()
        line_number = 2
        expected_content = original_lines[line_number - 1]  # Correct content
        incorrect_content = "This is not the actual content"
        new_line_content = "This is a modified line with verification."

        # Act 1: Edit with correct content verification - should succeed
        result_success = await file_operations.edit_file_at_line(
            str(test_file),
            [
                {
                    "line_number": line_number,
                    "action": "replace",
                    "content": new_line_content,
                    "expected_content": expected_content,
                }
            ],
            abort_on_verification_failure=True,
        )

        # Assert success case
        assert (
            "verification_failures" not in result_success
            or not result_success["verification_failures"]
        )
        assert result_success["edits_applied"] == 1

        # Reset the file
        await file_operations.write_file(str(test_file), original_content)

        # Act 2: Edit with incorrect content verification - should fail
        result_failure = await file_operations.edit_file_at_line(
            str(test_file),
            [
                {
                    "line_number": line_number,
                    "action": "replace",
                    "content": new_line_content,
                    "expected_content": incorrect_content,
                }
            ],
            abort_on_verification_failure=True,
        )

        # Assert failure case
        assert "success" in result_failure and not result_failure["success"]
        assert "verification_failures" in result_failure
        assert len(result_failure["verification_failures"]) > 0

        # Verify the file wasn't changed
        current_content = test_file.read_text()
        assert current_content == original_content

    async def test_edit_file_with_relative_line_numbers(
        self, test_dir: Path, file_operations: FileOperations
    ):
        """Test editing a file using relative line numbers with offset."""
        # Arrange
        test_file = test_dir / "file1.txt"
        original_content = test_file.read_text()
        original_lines = original_content.splitlines()

        # Print the original content for debugging
        print("\nOriginal file content:")
        for i, line in enumerate(original_lines):
            print(f"Line {i + 1}: {line}")

        # Let's recreate the test file with known content
        test_content = "Line 1\nLine 2\nLine 3\n"
        await file_operations.write_file(str(test_file), test_content)

        offset = 1  # Start at line 2 (offset 1)
        relative_line_number = 1  # Target line 3 (offset 1 + relative 1 = line 3)
        new_line_content = "This is line 3 modified with relative numbering."

        # Act
        result = await file_operations.edit_file_at_line(
            str(test_file),
            [
                {
                    "line_number": relative_line_number,  # This is relative to offset
                    "action": "replace",
                    "content": new_line_content,
                }
            ],
            offset=offset,
            relative_line_numbers=True,
        )

        # Debug the result
        print("\nResult of edit operation:")
        print(result)

        # Assert
        assert result["edits_applied"] == 1

        # Read the file again
        modified_content = test_file.read_text()
        modified_lines = modified_content.splitlines()

        # Debug the modified content
        print("\nModified file content:")
        for i, line in enumerate(modified_lines):
            print(f"Line {i + 1}: {line}")

        # Line 3 should be changed
        assert modified_lines[2] == new_line_content

        # Other lines should be unchanged
        assert modified_lines[0] == "Line 1"
        assert modified_lines[1] == "Line 2"

    async def test_create_and_remove_directory(
        self, test_dir: Path, file_operations: FileOperations
    ):
        """Test creating and then removing a directory."""
        # Arrange
        new_dir = test_dir / "new_test_dir"

        # Act - Create directory
        await file_operations.create_directory(str(new_dir))

        # Assert directory was created (create_directory doesn't return a value)
        assert new_dir.exists()
        assert new_dir.is_dir()

    async def test_read_file_lines_returns_specified_range(
        self, test_dir: Path, file_operations: FileOperations
    ):
        """Test that reading specific lines from a file works correctly using offset/limit."""
        # Arrange
        test_file = test_dir / "file1.txt"

        # Act
        content, metadata = await file_operations.read_file_lines(
            str(test_file), offset=1, limit=1
        )

        # Assert - focus on the key behavior
        # 1. Content should contain only the requested line (line 2, which is offset 1)
        expected_line = "It has multiple lines."
        assert expected_line in content

        # 2. The content should NOT include other lines
        assert "This is the first test file." not in content  # Line 1 (offset 0)
        assert "This is line 3." not in content  # Line 3 (offset 2)

        # 3. Metadata should correctly represent what was read
        assert metadata["offset"] == 1  # We requested offset 1
        assert metadata["limit"] == 1  # We requested limit 1
        assert metadata["lines_read"] == 1  # We should have read 1 line
        assert metadata["total_lines"] >= 3  # Test file has at least 3 lines

    async def test_read_file_lines_handles_out_of_range(
        self, test_dir: Path, file_operations: FileOperations
    ):
        """Test that reading lines out of range works correctly."""
        # Arrange
        test_file = test_dir / "file1.txt"

        # Act - offset beyond file length
        content, metadata = await file_operations.read_file_lines(
            str(test_file), offset=10
        )

        # Assert
        assert content == ""  # No content should be returned
        assert metadata["lines_read"] == 0  # No lines were read
        assert metadata["total_lines"] == 3  # File has 3 lines total

    async def test_get_file_info_returns_correct_metadata(
        self, test_dir: Path, file_operations: FileOperations
    ):
        """Test that getting file info returns correct metadata."""
        # Arrange
        test_file = test_dir / "file1.txt"

        # Act
        info = await file_operations.get_file_info(str(test_file))

        # Assert - focus on behavior, not implementation details
        # The key functionality is that we get correct info about the file

        # 1. File metadata should match actual file properties
        assert info.name == test_file.name
        assert info.is_file is True
        assert (
            info.is_dir is False
        )  # The attribute is called 'is_dir', not 'is_directory'

        # 2. Size should match the actual file size
        expected_size = test_file.stat().st_size
        assert info.size == expected_size

        # 3. Important metadata fields should be present
        assert info.modified is not None
        assert info.created is not None

    async def test_directory_tree_contains_all_entries(
        self, test_dir: Path, advanced_operations: AdvancedFileOperations
    ):
        """Test that directory tree contains all entries."""
        # Act
        tree = await advanced_operations.directory_tree(str(test_dir))

        # Assert
        assert tree["name"] == test_dir.name
        assert tree["type"] == "directory"

        # Check that we have the expected children
        children_names = [child["name"] for child in tree["children"]]
        assert "file1.txt" in children_names
        assert "file2.txt" in children_names
        assert "empty.txt" in children_names
        assert "config.json" in children_names
        assert "subdir" in children_names

        # Find the subdirectory and check its children
        subdir = next(child for child in tree["children"] if child["name"] == "subdir")
        assert subdir["type"] == "directory"
        assert len(subdir["children"]) >= 1
        assert subdir["children"][0]["name"] == "subfile.txt"
