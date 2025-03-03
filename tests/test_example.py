from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_filesystem.security import PathValidator
from mcp_filesystem.operations import FileOperations


@pytest.fixture
def path_validator():
    validator = PathValidator(["/test/allowed"])
    return validator


@pytest.fixture
def file_operations(path_validator):
    return FileOperations(path_validator)


@pytest.mark.asyncio
async def test_read_file_lines(file_operations):
    # Mock the validation to return a success
    file_operations.validator.validate_path = AsyncMock(
        return_value=(Path("/test/allowed/file.txt"), True)
    )

    # Mock the file operations
    with (
        patch("anyio.to_thread.run_sync") as mock_run_sync,
        patch("anyio.open_file") as mock_open,
    ):
        # Mocking the file stats
        mock_stat = MagicMock()
        mock_stat.st_size = 100
        mock_run_sync.return_value = mock_stat

        # Mock file content
        mock_file = AsyncMock()
        mock_file.__aenter__.return_value = mock_file
        mock_file.readline.side_effect = [b"line1\n", b"line2\n", b"line3\n", b""]
        mock_file.read.return_value = b"line2\nline3\n"
        mock_open.return_value = mock_file

        # Call the function
        content, metadata = await file_operations.read_file_lines(
            "/test/allowed/file.txt", offset=1, limit=2
        )

        # Assert the results
        assert content == "line2\nline3\n"
        assert metadata["offset"] == 1
        assert metadata["limit"] == 2
        assert metadata["total_lines"] == 3
        assert metadata["lines_read"] == 2
