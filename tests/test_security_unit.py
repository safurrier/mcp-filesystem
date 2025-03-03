"""Unit tests for the security module.

These tests verify that the PathValidator correctly enforces
security constraints and prevents access to files outside
allowed directories using behavior-driven testing.
"""

import os
from pathlib import Path
import tempfile
from typing import List, Dict, Optional, Any
import pytest

from mcp_filesystem.security import PathValidator


@pytest.fixture
def secure_filesystem():
    """Create a temporary filesystem for security testing.
    
    This fixture provides a real filesystem with a standard set of
    test directories and files to avoid excessive mocking.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        base_dir = Path(temp_dir)
        
        # Create standard directory structure
        allowed_dir1 = base_dir / "allowed1"
        allowed_dir2 = base_dir / "allowed2"
        outside_dir = base_dir / "outside"
        
        # Create directories
        allowed_dir1.mkdir()
        allowed_dir2.mkdir()
        outside_dir.mkdir()
        
        # Create nested directories
        nested_dir = allowed_dir1 / "nested"
        nested_dir.mkdir()
        
        # Create test files
        (allowed_dir1 / "test1.txt").write_text("Test file in allowed1")
        (allowed_dir1 / "test2.md").write_text("Markdown in allowed1")
        (allowed_dir2 / "test3.txt").write_text("Test file in allowed2")
        (nested_dir / "nested.txt").write_text("Nested file")
        (outside_dir / "outside.txt").write_text("File outside allowed dirs")
        
        # Create directory structure for traversal testing
        traversal_dir = allowed_dir1 / "traversal" / "subdir"
        traversal_dir.mkdir(parents=True)
        (traversal_dir / "deep.txt").write_text("Deep file")
        (allowed_dir1 / "traversal" / "parent.txt").write_text("Parent file")
        
        # Try to create symlinks if possible
        try:
            # Create good symlink (within allowed dir)
            good_link = allowed_dir1 / "good_link.txt"
            os.symlink(str(allowed_dir1 / "test1.txt"), str(good_link))
            
            # Create bad symlink (points outside allowed dirs)
            bad_link = allowed_dir1 / "bad_link.txt"
            os.symlink(str(outside_dir / "outside.txt"), str(bad_link))
            
            symlinks_supported = True
        except (OSError, AttributeError):
            # Symlinks not supported on this platform or user lacks permissions
            symlinks_supported = False
        
        yield {
            "base_dir": base_dir,
            "allowed_dir1": allowed_dir1,
            "allowed_dir2": allowed_dir2,
            "outside_dir": outside_dir,
            "nested_dir": nested_dir,
            "traversal_dir": traversal_dir,
            "symlinks_supported": symlinks_supported
        }


@pytest.mark.asyncio
class TestPathValidator:
    """Test the PathValidator using a real filesystem."""
    
    async def test_validate_paths_within_allowed_directory(self, secure_filesystem):
        """Test validating paths within allowed directories."""
        # Arrange
        fs = secure_filesystem
        validator = PathValidator([
            str(fs["allowed_dir1"]), 
            str(fs["allowed_dir2"])
        ])
        
        # Test cases for allowed paths
        allowed_paths = [
            # Files directly in allowed directories
            str(fs["allowed_dir1"] / "test1.txt"),
            str(fs["allowed_dir2"] / "test3.txt"),
            # Files in subdirectories of allowed directories
            str(fs["nested_dir"] / "nested.txt"),
            # Directories
            str(fs["nested_dir"]),
        ]
        
        # Act & Assert
        for path in allowed_paths:
            result_path, allowed = await validator.validate_path(path)
            assert allowed is True, f"Path should be allowed: {path}"
            assert Path(result_path).exists(), f"Path should exist: {path}"
    
    async def test_validate_paths_outside_allowed_directory(self, secure_filesystem):
        """Test validating paths outside allowed directories."""
        # Arrange
        fs = secure_filesystem
        validator = PathValidator([
            str(fs["allowed_dir1"]), 
            str(fs["allowed_dir2"])
        ])
        
        # Test cases for disallowed paths
        disallowed_paths = [
            # Files outside allowed directories
            str(fs["outside_dir"] / "outside.txt"),
            # Parent of allowed directory
            str(fs["base_dir"]),
            # Nonexistent path outside allowed directories
            str(fs["outside_dir"] / "nonexistent.txt"),
        ]
        
        # Act & Assert
        for path in disallowed_paths:
            result_path, allowed = await validator.validate_path(path)
            assert allowed is False, f"Path should be disallowed: {path}"
    
    async def test_validate_path_with_symlinks(self, secure_filesystem):
        """Test validating paths with symlinks."""
        # Skip test if symlinks aren't supported
        if not secure_filesystem["symlinks_supported"]:
            pytest.skip("Symlinks not supported on this platform")
        
        # Arrange
        fs = secure_filesystem
        validator = PathValidator([
            str(fs["allowed_dir1"]), 
            str(fs["allowed_dir2"])
        ])
        
        # Symlink within allowed directory
        good_link = fs["allowed_dir1"] / "good_link.txt"
        
        # Symlink to file outside allowed directory
        bad_link = fs["allowed_dir1"] / "bad_link.txt"
        
        # Act & Assert
        # Good symlink should be allowed
        result_path, allowed = await validator.validate_path(str(good_link))
        assert allowed is True, "Symlink to file within allowed directory should be allowed"
        
        # Bad symlink should be disallowed
        result_path, allowed = await validator.validate_path(str(bad_link))
        assert allowed is False, "Symlink to file outside allowed directory should be disallowed"
    
    async def test_validate_nonexistent_paths(self, secure_filesystem):
        """Test validating nonexistent paths."""
        # Arrange
        fs = secure_filesystem
        validator = PathValidator([
            str(fs["allowed_dir1"]), 
            str(fs["allowed_dir2"])
        ])
        
        # Test cases for nonexistent paths
        test_cases = [
            # Nonexistent file in allowed directory (should be allowed for creation)
            {
                "path": str(fs["allowed_dir1"] / "new_file.txt"),
                "expected": True
            },
            # Nonexistent file outside allowed directories (should be disallowed)
            {
                "path": str(fs["outside_dir"] / "new_file.txt"),
                "expected": False
            },
        ]
        
        # Act & Assert
        for tc in test_cases:
            result_path, allowed = await validator.validate_path(tc["path"])
            assert allowed is tc["expected"], f"Failed for path: {tc['path']}"
    
    async def test_validate_relative_paths(self, secure_filesystem):
        """Test validating relative paths with potential directory traversal."""
        # Arrange
        fs = secure_filesystem
        validator = PathValidator([
            str(fs["allowed_dir1"]), 
            str(fs["allowed_dir2"])
        ])
        
        # Create a test file that has a known current directory
        cwd = fs["traversal_dir"]
        os.chdir(str(cwd))
        
        # Test cases for relative paths
        test_cases = [
            # Simple relative path in current directory (should be allowed)
            {
                "path": "deep.txt",
                "expected": True
            },
            # Go up one level but still within allowed directory (should be allowed)
            {
                "path": "../parent.txt",
                "expected": True
            },
            # Go up multiple levels trying to escape (should be disallowed)
            {
                "path": "../../../outside/outside.txt",
                "expected": False
            },
        ]
        
        # Act & Assert
        for tc in test_cases:
            result_path, allowed = await validator.validate_path(tc["path"])
            assert allowed is tc["expected"], f"Failed for relative path: {tc['path']}"
    
    async def test_pattern_matching_with_globs(self, secure_filesystem):
        """Test file pattern matching with glob patterns."""
        # Arrange
        fs = secure_filesystem
        validator = PathValidator([
            str(fs["allowed_dir1"]), 
            str(fs["allowed_dir2"])
        ])
        
        # Test behaviors rather than exact counts
        
        # Test 1: Non-recursive text file matching in allowed_dir1
        result1 = await validator.find_matching_files(
            str(fs["allowed_dir1"]), 
            "*.txt", 
            recursive=False
        )
        # Verify behavior: should find at least test1.txt
        test1_file_name = fs["allowed_dir1"] / "test1.txt"
        assert any(test1_file_name.name == path.name for path in result1), \
            f"Should find {test1_file_name.name} in non-recursive search"
        # Verify behavior: shouldn't find files in subdirectories
        assert not any(fs["nested_dir"].name in str(path) for path in result1), \
            "Non-recursive search shouldn't include nested directories"
            
        # Test 2: Recursive text file matching
        result2 = await validator.find_matching_files(
            str(fs["allowed_dir1"]), 
            "**/*.txt", 
            recursive=True
        )
        # Verify behavior: should find more files with recursive search
        assert len(result2) > len(result1), "Recursive search should find more files"
        # Verify behavior: should find files in subdirectories
        nested_file_name = fs["nested_dir"] / "nested.txt"
        assert any(nested_file_name.name == path.name and fs["nested_dir"].name in str(path) 
                  for path in result2), \
            f"Should find {nested_file_name.name} in recursive search"
            
        # Test 3: Exclude patterns
        result3 = await validator.find_matching_files(
            str(fs["allowed_dir1"]), 
            "*.txt", 
            recursive=False,
            exclude_patterns=["test*"]
        )
        # Verify behavior: excluding test* should filter out test1.txt
        assert not any("test1.txt" in str(path) for path in result3), \
            "Exclude pattern should filter out matching files"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])