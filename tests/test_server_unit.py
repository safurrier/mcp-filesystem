"""Unit tests for the server module.

These tests verify that the MCP server correctly exposes file
operations to clients and handles errors properly, focusing on
behavior rather than implementation details.
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from fastmcp import Context

from mcp_filesystem.server import (
    mcp, 
    get_components, 
    get_allowed_dirs,
    read_file,
    write_file,
    list_directory,
    move_file,
    edit_file_at_line,
    grep_files,
    read_file_lines,
    get_file_info,
)
from mcp_filesystem.security import PathValidator
from mcp_filesystem.operations import FileOperations
from mcp_filesystem.grep import GrepTools, GrepResult, GrepMatch


class MockContext:
    """Mock Context for MCP testing."""
    
    def __init__(self, **kwargs):
        """Initialize with optional attributes."""
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def mock_context():
    """Create a mock MCP context."""
    return MockContext()


@pytest.fixture
def mock_components():
    """Create mock components for testing."""
    # Create mock validator, operations, and grep tools
    validator = MagicMock(spec=PathValidator)
    operations = MagicMock(spec=FileOperations)
    grep = MagicMock(spec=GrepTools)
    advanced = MagicMock()
    
    # Configure common behavior
    validator.get_allowed_dirs.return_value = ["/test"]
    
    # Create the components dict
    components = {
        "validator": validator,
        "operations": operations,
        "grep": grep,
        "advanced": advanced,
        "allowed_dirs": ["/test"],
    }
    
    return components


@pytest.fixture
def test_filesystem():
    """Create a temporary filesystem for testing.
    
    This fixture provides a real filesystem for tests, avoiding
    excessive mocking of file operations.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        base_dir = Path(temp_dir)
        
        # Set up standard file structure
        test_file = base_dir / "test.txt"
        test_file.write_text("This is a test file\nWith multiple lines\nFor testing")
        
        # Create a subdirectory
        subdir = base_dir / "subdir"
        subdir.mkdir()
        (subdir / "subfile.txt").write_text("File in subdirectory")
        
        # Create a file with search terms
        grep_file = base_dir / "searchable.txt"
        grep_file.write_text(
            "This line has a search term\n"
            "This line doesn't match\n"
            "Another line with search term\n"
        )
        
        yield base_dir


@pytest.mark.asyncio
class TestServerCore:
    """Tests for server core functionality."""
    
    @patch('sys.argv', ['server.py'])  # Override command line args for test
    async def test_get_allowed_dirs_from_environment(self):
        """Verify that allowed directories are correctly retrieved from environment.
        
        This test focuses on behavior: given environment variables,
        does get_allowed_dirs return the expected directories?
        """
        # Arrange
        test_dirs = "/test/dir1:/test/dir2"
        
        # Act - use patch to temporarily set environment variable
        with patch.dict(os.environ, {"MCP_ALLOWED_DIRS": test_dirs}), \
             patch('sys.argv', ['server.py']):  # Ensure no command-line args
            result = get_allowed_dirs()
        
        # Assert - focus on behavior
        assert "/test/dir1" in result
        assert "/test/dir2" in result
        assert all(d.startswith("/test/") for d in result)
    
    @patch('sys.argv', ['server.py'])  # Override command line args for test
    async def test_get_allowed_dirs_default_to_cwd(self):
        """Verify that allowed directories default to current directory when none specified."""
        # Arrange - temporarily clear the environment variable
        test_dir = "/current/dir"
        
        with patch.dict(os.environ, {"MCP_ALLOWED_DIRS": ""}), \
             patch('os.getcwd', return_value=test_dir), \
             patch('sys.argv', ['server.py']):  # Ensure no command-line args
            
            # Act
            result = get_allowed_dirs()
        
        # Assert - only care if the current directory is included
        assert test_dir in result
    
    async def test_get_components_provides_required_components(self):
        """Verify that get_components returns all required components.
        
        This test focuses on the behavior (returning necessary components)
        rather than implementation details (like caching).
        """
        # Act - clear cache and get new components
        from mcp_filesystem.server import _components_cache
        _components_cache.clear()
        
        # Override allowed dirs to avoid real file access
        with patch('mcp_filesystem.server.get_allowed_dirs', return_value=["/test"]):
            components = get_components()
        
        # Assert - focus on behavior, not implementation
        assert "validator" in components
        assert "operations" in components 
        assert "grep" in components
        assert "advanced" in components
        assert "allowed_dirs" in components
        
        # Clean up for other tests
        _components_cache.clear()


@pytest.mark.asyncio
class TestServerTools:
    """Tests for server tool functions."""
    
    async def test_read_file_returns_content(self, mock_context, mock_components):
        """Verify read_file tool returns file content."""
        # Arrange
        test_path = "/test/file.txt"
        expected_content = "File content"
        
        # Configure operations mock
        mock_components["operations"].read_file = AsyncMock(return_value=expected_content)
        
        # Act
        with patch('mcp_filesystem.server.get_components', return_value=mock_components):
            result = await read_file(test_path, mock_context)
        
        # Assert - focus on expected behavior
        assert result == expected_content
    
    async def test_read_file_handles_errors(self, mock_context, mock_components):
        """Verify read_file tool handles exceptions gracefully."""
        # Arrange
        test_path = "/test/invalid.txt"
        
        # Configure operations mock to raise exception
        mock_components["operations"].read_file = AsyncMock(
            side_effect=ValueError("Invalid path")
        )
        
        # Act
        with patch('mcp_filesystem.server.get_components', return_value=mock_components):
            result = await read_file(test_path, mock_context)
        
        # Assert - check behavior
        assert "Error" in result
        assert "path" in result.lower() or "Invalid" in result
    
    async def test_write_file_with_real_filesystem(self, mock_context, test_filesystem):
        """Test write_file using a real filesystem to verify behavior.
        
        This tests actual behavior rather than implementation details.
        """
        # Arrange
        test_path = str(test_filesystem / "new_file.txt")
        test_content = "New test content"
        
        # Create real components with the test filesystem
        validator = PathValidator([str(test_filesystem)])
        operations = FileOperations(validator)
        
        components = {
            "validator": validator,
            "operations": operations,
            "allowed_dirs": [str(test_filesystem)]
        }
        
        # Act - write to a real file
        with patch('mcp_filesystem.server.get_components', return_value=components):
            result = await write_file(test_path, test_content, mock_context)
        
        # Assert - verify the file was actually written
        assert Path(test_path).exists()
        assert Path(test_path).read_text() == test_content
        assert "success" in result.lower()
    
    async def test_list_directory_with_real_filesystem(self, mock_context, test_filesystem):
        """Test list_directory with real filesystem to verify behavior."""
        # Arrange
        validator = PathValidator([str(test_filesystem)])
        operations = FileOperations(validator)
        
        components = {
            "validator": validator,
            "operations": operations,
            "allowed_dirs": [str(test_filesystem)]
        }
        
        # Act - list real directory
        with patch('mcp_filesystem.server.get_components', return_value=components):
            # Test text format
            text_result = await list_directory(str(test_filesystem), mock_context, format="text")
            # Test JSON format
            json_result = await list_directory(str(test_filesystem), mock_context, format="json")
        
        # Assert - focus on behavior
        # Text format should contain expected files
        assert "test.txt" in text_result
        assert "subdir" in text_result
        assert "searchable.txt" in text_result
        
        # JSON format should be parseable and contain expected files
        parsed = json.loads(json_result)
        assert isinstance(parsed, list)
        file_names = [entry["name"] for entry in parsed]
        assert "test.txt" in file_names
        assert "subdir" in file_names
        assert "searchable.txt" in file_names
    
    async def test_grep_files_finds_matches(self, mock_context, test_filesystem):
        """Test grep_files with real filesystem to verify behavior."""
        # Arrange - create real components
        validator = PathValidator([str(test_filesystem)])
        operations = FileOperations(validator)
        grep = GrepTools(validator)
        
        components = {
            "validator": validator,
            "operations": operations,
            "grep": grep,
            "allowed_dirs": [str(test_filesystem)]
        }
        
        # The test file contains two lines with "search term"
        test_path = str(test_filesystem / "searchable.txt")
        test_pattern = "search term"
        
        # Act - search with real grep functionality
        with patch('mcp_filesystem.server.get_components', return_value=components):
            result = await grep_files(test_path, test_pattern, mock_context)
        
        # Assert - focus on behavior: did it find the expected matches?
        assert "search term" in result
        assert "2 matches" in result.lower() or "matches: 2" in result.lower()
    
    async def test_edit_file_at_line_applies_edits(self, mock_context, test_filesystem):
        """Test edit_file_at_line with real filesystem to verify behavior."""
        # Arrange - create a file with known content
        test_path = str(test_filesystem / "edit_test.txt")
        Path(test_path).write_text("Line 1\nLine 2\nLine 3\n")
        
        # Create real components
        validator = PathValidator([str(test_filesystem)])
        operations = FileOperations(validator)
        
        components = {
            "validator": validator,
            "operations": operations,
            "allowed_dirs": [str(test_filesystem)]
        }
        
        # Define line edits to apply
        line_edits = [
            {"line_number": 2, "action": "replace", "content": "Modified Line 2"}
        ]
        
        # Act - edit the file
        with patch('mcp_filesystem.server.get_components', return_value=components):
            result = await edit_file_at_line(test_path, line_edits, mock_context)
        
        # Assert - verify the file was actually edited
        file_content = Path(test_path).read_text()
        expected_content = "Line 1\nModified Line 2\nLine 3\n"
        assert file_content == expected_content
        assert "edits" in result.lower()
        assert "applied" in result.lower()
    
    async def test_read_file_lines_returns_specific_lines(self, mock_context, test_filesystem):
        """Test read_file_lines with real filesystem to verify behavior."""
        # Arrange - create a file with multiple lines
        test_path = str(test_filesystem / "lines_test.txt")
        test_content = "\n".join([f"Line {i}" for i in range(1, 11)])
        Path(test_path).write_text(test_content)
        
        # Create real components
        validator = PathValidator([str(test_filesystem)])
        operations = FileOperations(validator)
        
        components = {
            "validator": validator,
            "operations": operations,
            "allowed_dirs": [str(test_filesystem)]
        }
        
        # Act - read specific lines
        with patch('mcp_filesystem.server.get_components', return_value=components):
            result = await read_file_lines(
                test_path, mock_context, offset=2, limit=3
            )
        
        # Assert - verify correct lines are returned
        # Should include lines 3, 4, 5 (offset 2, limit 3)
        assert "Line 3" in result
        assert "Line 4" in result
        assert "Line 5" in result
        assert "Line 1" not in result
        assert "Line 6" not in result
    
    async def test_get_file_info_returns_metadata(self, mock_context, test_filesystem):
        """Test get_file_info with real filesystem to verify behavior."""
        # Arrange - create file with known content
        test_path = str(test_filesystem / "info_test.txt")
        test_content = "This is a test file for get_file_info"
        Path(test_path).write_text(test_content)
        
        # Create real components
        validator = PathValidator([str(test_filesystem)])
        operations = FileOperations(validator)
        
        components = {
            "validator": validator,
            "operations": operations,
            "allowed_dirs": [str(test_filesystem)]
        }
        
        # Act - get file info
        with patch('mcp_filesystem.server.get_components', return_value=components):
            text_result = await get_file_info(test_path, mock_context, format="text")
            json_result = await get_file_info(test_path, mock_context, format="json")
        
        # Assert - verify metadata is correct
        # Text format should contain basic info
        assert "File" in text_result
        assert Path(test_path).name in text_result
        assert "Size" in text_result
        
        # JSON format should be valid and contain expected fields
        parsed = json.loads(json_result)
        assert parsed["name"] == Path(test_path).name
        assert parsed["size"] == len(test_content)
        assert parsed["is_file"] is True
        assert "created" in parsed
        assert "modified" in parsed


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])