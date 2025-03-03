"""Unit tests for FileOperations class.

These tests verify the core file operations functionality using behavioral
testing techniques focused on outcomes rather than implementation details.
"""

import os
import json
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

import anyio

from mcp_filesystem.operations import FileOperations, FileInfo
from mcp_filesystem.security import PathValidator


@pytest.fixture
def test_fs():
    """Create a temporary filesystem for testing file operations.
    
    This fixture provides a real filesystem with a standard set of
    test files and directories to avoid excessive mocking.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        base_dir = Path(temp_dir)
        
        # Create test files
        test_file = base_dir / "test.txt"
        test_file.write_text("This is a test file\nWith multiple lines\nFor testing")
        
        # Create a subdirectory with content
        subdir = base_dir / "subdir"
        subdir.mkdir()
        (subdir / "subfile.txt").write_text("File in subdirectory")
        
        # Create a file for editing
        edit_file = base_dir / "edit.txt"
        edit_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")
        
        # Create a large file with many lines for testing read_file_lines
        lines_file = base_dir / "lines.txt"
        lines_file.write_text("\n".join([f"Line {i}" for i in range(1, 101)]))
        
        # Create a directory for move operations
        move_dir = base_dir / "move_test"
        move_dir.mkdir()
        
        yield base_dir


@pytest.fixture
def file_operations(test_fs):
    """Create a FileOperations instance with the test filesystem."""
    validator = PathValidator([str(test_fs)])
    return FileOperations(validator)


@pytest.mark.asyncio
class TestFileOperations:
    """Unit tests for FileOperations class using behavioral testing."""
    
    async def test_read_file_returns_content(self, file_operations, test_fs):
        """Test that read_file returns the correct file content."""
        # Arrange
        test_path = str(test_fs / "test.txt")
        expected_content = "This is a test file\nWith multiple lines\nFor testing"
        
        # Act
        content = await file_operations.read_file(test_path)
        
        # Assert - focus on behavior, not implementation
        assert content == expected_content
    
    async def test_read_file_raises_error_for_nonexistent_file(self, file_operations, test_fs):
        """Test that read_file raises appropriate error for nonexistent files."""
        # Arrange
        test_path = str(test_fs / "nonexistent.txt")
        
        # Act/Assert
        with pytest.raises(FileNotFoundError):
            await file_operations.read_file(test_path)
    
    async def test_read_file_with_different_encoding(self, file_operations, test_fs):
        """Test read_file with different encoding."""
        # Arrange
        test_path = str(test_fs / "encoded.txt")
        test_content = "Café Français"  # Content with non-ASCII characters
        
        # Create a file with specific encoding
        Path(test_path).write_bytes(test_content.encode('latin-1'))
        
        # Act
        content = await file_operations.read_file(test_path, encoding='latin-1')
        
        # Assert
        assert content == test_content
    
    async def test_write_file_creates_new_file(self, file_operations, test_fs):
        """Test that write_file creates a new file with correct content."""
        # Arrange
        test_path = str(test_fs / "new_file.txt")
        test_content = "New file content"
        
        # Act
        await file_operations.write_file(test_path, test_content)
        
        # Assert - check the file was actually created with correct content
        assert Path(test_path).exists()
        assert Path(test_path).read_text() == test_content
    
    async def test_write_file_with_create_dirs(self, file_operations, test_fs):
        """Test write_file with create_dirs option."""
        # Arrange
        new_dir = test_fs / "new_directory"
        test_path = str(new_dir / "nested_file.txt")
        test_content = "Content in a nested directory"
        
        # Act
        await file_operations.write_file(test_path, test_content, create_dirs=True)
        
        # Assert
        assert new_dir.exists()
        assert new_dir.is_dir()
        assert Path(test_path).exists()
        assert Path(test_path).read_text() == test_content
    
    async def test_list_directory_returns_file_entries(self, file_operations, test_fs):
        """Test that list_directory returns correct file and directory entries."""
        # Arrange - we already have a test filesystem set up
        
        # Act
        entries = await file_operations.list_directory(str(test_fs))
        
        # Assert - check behavior, not implementation
        assert isinstance(entries, list)
        
        # Check the basic files we created are listed
        file_names = [entry["name"] for entry in entries]
        assert "test.txt" in file_names
        assert "subdir" in file_names
        assert "edit.txt" in file_names
        assert "lines.txt" in file_names
        
        # Verify the entries have the expected structure
        for entry in entries:
            if entry["name"] == "subdir":
                assert entry["is_directory"] is True
            elif entry["name"] == "test.txt":
                assert entry["is_file"] is True
                assert entry["size"] > 0
    
    async def test_list_directory_with_pattern_filter(self, file_operations, test_fs):
        """Test list_directory with a pattern filter."""
        # Arrange
        # Create additional files of different types for pattern matching
        (test_fs / "doc1.md").write_text("Markdown file")
        (test_fs / "doc2.md").write_text("Another markdown file")
        
        # Act - filter by *.md pattern
        entries = await file_operations.list_directory(str(test_fs), pattern="*.md")
        
        # Assert
        assert len(entries) == 2
        file_names = [entry["name"] for entry in entries]
        assert "doc1.md" in file_names
        assert "doc2.md" in file_names
        assert "test.txt" not in file_names
    
    async def test_move_file(self, file_operations, test_fs):
        """Test moving a file from one location to another."""
        # Arrange
        source_path = str(test_fs / "move_source.txt")
        dest_path = str(test_fs / "move_test" / "move_destination.txt")
        test_content = "File to be moved"
        
        # Create a test file to move
        Path(source_path).write_text(test_content)
        
        # Act
        await file_operations.move_file(source_path, dest_path)
        
        # Assert
        assert not Path(source_path).exists()
        assert Path(dest_path).exists()
        assert Path(dest_path).read_text() == test_content
    
    async def test_get_file_info_returns_metadata(self, file_operations, test_fs):
        """Test that get_file_info returns correct file metadata."""
        # Arrange
        test_path = str(test_fs / "test.txt")
        
        # Act
        file_info = await file_operations.get_file_info(test_path)
        
        # Assert
        assert file_info.name == "test.txt"
        assert str(file_info.path).endswith("test.txt")
        assert file_info.is_file is True
        assert file_info.is_dir is False
        assert file_info.size > 0
        assert isinstance(file_info.created, datetime)
        assert isinstance(file_info.modified, datetime)
        assert isinstance(file_info.permissions, str)
        
        # Check the dict representation contains the same info
        info_dict = file_info.to_dict()
        assert info_dict["name"] == "test.txt"
        assert "size" in info_dict
        assert "created" in info_dict
        assert "modified" in info_dict
    
    async def test_read_file_lines_with_offset_and_limit(self, file_operations, test_fs):
        """Test reading specific lines from a file with offset and limit."""
        # Arrange
        test_path = str(test_fs / "lines.txt")
        offset = 5  # Start at line 6 (0-indexed)
        limit = 3   # Read 3 lines
        
        # Act
        content, metadata = await file_operations.read_file_lines(test_path, offset, limit)
        
        # Assert
        # Check content behavior - should contain lines 6-8, allowing for potential trailing newline
        assert "Line 6" in content
        assert "Line 7" in content 
        assert "Line 8" in content
        assert "Line 5" not in content
        assert "Line 9" not in content
        
        # Check metadata behavior rather than exact implementation
        assert metadata["offset"] == offset
        assert metadata["limit"] == limit
        assert metadata["lines_read"] == limit
    
    async def test_edit_file_at_line_replaces_line(self, file_operations, test_fs):
        """Test editing a specific line in a file."""
        # Arrange
        test_path = str(test_fs / "edit.txt")
        # Reset the file to a known state
        original_content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        Path(test_path).write_text(original_content)
        
        line_edits = [
            {"line_number": 2, "action": "replace", "content": "Modified Line 2"}
        ]
        
        # Act
        result = await file_operations.edit_file_at_line(test_path, line_edits)
        
        # Assert
        # Check the file was modified correctly by verifying behavior
        new_content = Path(test_path).read_text()
        assert "Modified Line 2" in new_content
        assert "Line 1" in new_content  # Unchanged line
        assert "Line 3" in new_content  # Unchanged line
        
        # Check line 2 was replaced by verifying line ordering
        lines = new_content.splitlines()
        assert lines[0] == "Line 1"
        assert lines[1] == "Modified Line 2"
        assert lines[2] == "Line 3"
        
        # Check the result contains correct metadata
        assert result["edits_applied"] == 1
        # Allow for macOS /var vs /private/var path normalization
        assert Path(result["path"]).name == Path(test_path).name
        changes = result.get("changes", [])
        assert len(changes) == 1
        assert changes[0]["line"] == 2
        assert changes[0]["action"] == "replace"
    
    async def test_edit_file_at_line_with_verification(self, file_operations, test_fs):
        """Test line editing with content verification."""
        # Arrange
        test_path = str(test_fs / "edit.txt")
        
        # Edit with correct verification
        correct_edit = [
            {
                "line_number": 3, 
                "action": "replace", 
                "content": "Modified Line 3", 
                "expected_content": "Line 3"
            }
        ]
        
        # Edit with incorrect verification
        incorrect_edit = [
            {
                "line_number": 3, 
                "action": "replace", 
                "content": "Modified Line 3", 
                "expected_content": "Wrong content"
            }
        ]
        
        # Act - First try with correct verification
        result_success = await file_operations.edit_file_at_line(
            test_path, correct_edit, abort_on_verification_failure=True
        )
        
        # Get the content after successful edit
        content_after_success = Path(test_path).read_text()
        
        # Act - Now try with incorrect verification
        result_failure = await file_operations.edit_file_at_line(
            test_path, incorrect_edit, abort_on_verification_failure=True
        )
        
        # Get the content after failed edit
        content_after_failure = Path(test_path).read_text()
        
        # Assert
        # Successful edit should change the file
        assert "Modified Line 3" in content_after_success
        assert result_success["edits_applied"] == 1
        
        # Failed verification should not change the file
        assert content_after_success == content_after_failure
        assert not result_failure.get("success", True)
        assert "verification_failures" in result_failure
    
    async def test_edit_file_at_line_with_relative_numbering(self, file_operations, test_fs):
        """Test editing with relative line numbering."""
        # Arrange
        test_path = str(test_fs / "edit.txt")
        
        # Reset the content to ensure consistent state
        Path(test_path).write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")
        
        offset = 2  # Start at Line 3 (0-indexed position 2)
        
        # Edit with relative line numbers
        relative_edits = [
            {"line_number": 1, "action": "replace", "content": "Modified Line 4"}
        ]
        
        # Act
        result = await file_operations.edit_file_at_line(
            test_path, relative_edits, 
            offset=offset, relative_line_numbers=True
        )
        
        # Assert
        # Check content by verifying actual line ordering
        new_content = Path(test_path).read_text()
        lines = new_content.splitlines()
        
        assert lines[0] == "Line 1"
        assert lines[1] == "Line 2"
        assert lines[2] == "Line 3"
        assert lines[3] == "Modified Line 4"  # Fourth line should be modified
        assert lines[4] == "Line 5"
        
        # Check metadata
        assert result["edits_applied"] == 1
        changes = result.get("changes", [])
        # Line number in result should reference an absolute line number
        assert changes[0]["line"] == 4


@pytest.mark.asyncio
class TestFileInfo:
    """Tests for the FileInfo class."""
    
    async def test_fileinfo_gets_correct_metadata(self, test_fs):
        """Test that FileInfo correctly retrieves file metadata."""
        # Arrange - create a test file with known content
        test_file = test_fs / "fileinfo_test.txt"
        test_content = "Test content for FileInfo"
        test_file.write_text(test_content)
        
        # Act
        file_info = FileInfo(test_file)
        
        # Assert
        assert file_info.name == "fileinfo_test.txt"
        assert file_info.is_file is True
        assert file_info.is_dir is False
        assert file_info.size == len(test_content)
        assert isinstance(file_info.created, datetime)
        assert isinstance(file_info.modified, datetime)
        assert isinstance(file_info.permissions, str)
    
    async def test_fileinfo_for_directory(self, test_fs):
        """Test that FileInfo correctly identifies a directory."""
        # Arrange - use an existing directory
        test_dir = test_fs / "subdir"
        
        # Act
        dir_info = FileInfo(test_dir)
        
        # Assert
        assert dir_info.name == "subdir"
        assert dir_info.is_dir is True
        assert dir_info.is_file is False
    
    async def test_fileinfo_to_dict(self, test_fs):
        """Test FileInfo.to_dict returns a complete dictionary representation."""
        # Arrange
        test_file = test_fs / "fileinfo_dict.txt"
        test_file.write_text("Test content")
        
        # Act
        file_info = FileInfo(test_file)
        info_dict = file_info.to_dict()
        
        # Assert
        assert isinstance(info_dict, dict)
        assert info_dict["name"] == "fileinfo_dict.txt"
        assert info_dict["path"] == str(test_file)
        assert info_dict["is_file"] is True
        assert info_dict["is_directory"] is False
        assert "size" in info_dict
        assert "created" in info_dict
        assert "modified" in info_dict
        assert "permissions" in info_dict
    
    async def test_fileinfo_string_representation(self, test_fs):
        """Test the string representation of FileInfo."""
        # Arrange
        test_file = test_fs / "fileinfo_str.txt"
        test_file.write_text("Test content")
        
        # Act
        file_info = FileInfo(test_file)
        info_str = str(file_info)
        
        # Assert
        assert "File" in info_str
        assert "fileinfo_str.txt" in info_str
        assert "Size" in info_str
        assert "Created" in info_str
        assert "Modified" in info_str
        assert "Permissions" in info_str


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])