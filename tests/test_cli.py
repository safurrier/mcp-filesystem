"""Test the CLI interface for MCP Filesystem.

This test suite verifies the behavior of the CLI interface,
ensuring it works as expected from a user's perspective.
"""

import sys
import subprocess
import tempfile
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import pytest

@dataclass
class CLITestCase:
    """Test case for CLI interface behavior tests."""
    name: str
    args: list
    expected_in_output: list
    expected_not_in_output: Optional[list] = None
    expected_returncode: int = 0
    check_stderr: bool = False

@pytest.fixture
def temp_directory():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)

def run_cli_command(args, cwd=None):
    """Run the CLI command with the given arguments."""
    # Get repo root if no cwd provided
    if cwd is None:
        cwd = Path(__file__).parent.parent.absolute()
    
    # Use the run_server.py script directly
    cmd = [sys.executable, str(Path(cwd) / "run_server.py")] + args
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False  # We'll check the return code ourselves
    )
    return result

@pytest.mark.parametrize("case", [
    CLITestCase(
        name="help flag shows options",
        args=["--help"],
        expected_in_output=[
            "transport", 
            "port", 
            "debug",
            "directories"  # Should accept directories as arguments
        ],
        expected_not_in_output=["run [OPTIONS]"]  # No 'run' subcommand required
    ),
    CLITestCase(
        name="version flag shows version",
        args=["--version"],
        expected_in_output=["MCP Filesystem Server v"]
    )
])
def test_cli_behavior(case):
    """Test CLI behaviors using table-driven testing approach."""
    # Act
    result = run_cli_command(case.args)
    
    # Assert
    output = result.stderr if case.check_stderr else result.stdout
    output = output.lower()  # Case-insensitive matching to focus on content not format
    
    # Check expected content is present - focus on behaviors not exact strings
    for expected in case.expected_in_output:
        assert expected.lower() in output, f"Expected '{expected}' in output, but it was not found. Output: {output}"
    
    # Check unexpected content is absent
    if case.expected_not_in_output:
        for unexpected in case.expected_not_in_output:
            assert unexpected.lower() not in output, f"Found unexpected '{unexpected}' in output. Output: {output}"
    
    # Check return code
    assert result.returncode == case.expected_returncode, \
        f"Expected return code {case.expected_returncode}, got {result.returncode}. Error: {result.stderr}"

def test_direct_script_execution():
    """Test direct script execution without module invocation.
    
    This is the key behavioral change - users can run run_server.py directly
    without needing to use the -m module flag.
    """
    # Arrange - using the default repo root in run_cli_command
    
    # Act - Using --version as a simple, reliable command to test the interface
    result = run_cli_command(["--version"])
    
    # Assert - check that the command is recognized and executed successfully
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    assert "MCP Filesystem Server" in result.stdout, "Version information not found in output"