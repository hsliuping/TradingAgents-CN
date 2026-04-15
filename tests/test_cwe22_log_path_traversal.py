"""
PoC test for CWE-22: Path traversal in LogExportService.

Tests that read_log_file, export_logs, and delete_log_file properly
reject filenames containing path traversal sequences.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the project root to sys.path so we can import the service
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


import pytest


@pytest.fixture
def service_with_secret(tmp_path):
    """
    Create a LogExportService with a controlled log directory,
    and place a secret file outside the log directory to prove traversal.
    """
    from app.services.log_export_service import LogExportService

    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    # Create a legitimate log file inside log_dir
    legit_log = log_dir / "app.log"
    legit_log.write_text("INFO: test log entry\n")

    # Create a sensitive file OUTSIDE the log directory
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("SECRET_DATA_SHOULD_NOT_BE_READABLE")

    # Create a .log file outside log_dir (for delete bypass test)
    outside_log = tmp_path / "outside.log"
    outside_log.write_text("OUTSIDE_LOG_DATA")

    service = LogExportService(log_dir=str(log_dir))
    return service, log_dir, secret_file, outside_log, tmp_path


class TestPathTraversalRead:
    """Tests for path traversal in read_log_file."""

    def test_read_traversal_relative(self, service_with_secret):
        """read_log_file with '../secret.txt' should be blocked."""
        service, log_dir, secret_file, _, _ = service_with_secret
        # Verify the secret is reachable via traversal
        traversal_path = log_dir / "../secret.txt"
        assert traversal_path.resolve().exists(), "Precondition: secret file must exist"

        with pytest.raises((ValueError, FileNotFoundError, PermissionError)):
            service.read_log_file(filename="../secret.txt")

    def test_read_traversal_absolute(self, service_with_secret):
        """read_log_file with an absolute path should be blocked."""
        service, _, secret_file, _, _ = service_with_secret

        with pytest.raises((ValueError, FileNotFoundError, PermissionError)):
            service.read_log_file(filename=str(secret_file))

    def test_read_traversal_double_dot(self, service_with_secret):
        """read_log_file with nested traversal should be blocked."""
        service, _, _, _, tmp_path = service_with_secret
        with pytest.raises((ValueError, FileNotFoundError, PermissionError)):
            service.read_log_file(filename="subdir/../../secret.txt")

    def test_read_legitimate_file(self, service_with_secret):
        """read_log_file with a normal log filename should work."""
        service, _, _, _, _ = service_with_secret
        result = service.read_log_file(filename="app.log")
        assert result["filename"] == "app.log"
        assert any("test log entry" in line for line in result["lines"])


class TestPathTraversalExport:
    """Tests for path traversal in export_logs."""

    def test_export_traversal(self, service_with_secret):
        """export_logs with traversal filenames should be blocked."""
        service, log_dir, secret_file, _, _ = service_with_secret
        traversal_path = log_dir / "../secret.txt"
        assert traversal_path.resolve().exists()

        with pytest.raises((ValueError, FileNotFoundError, PermissionError)):
            service.export_logs(filenames=["../secret.txt"])


class TestPathTraversalDelete:
    """Tests for path traversal in the delete endpoint."""

    def test_validate_log_path_rejects_traversal(self, service_with_secret):
        """
        _validate_log_path with '../outside.log' should raise even though
        the filename ends with .log.
        """
        service, log_dir, _, outside_log, _ = service_with_secret
        assert outside_log.exists(), "Precondition: outside.log must exist"

        try:
            validated = service._validate_log_path("../outside.log")
            pytest.fail("_validate_log_path should have rejected '../outside.log'")
        except AttributeError:
            pytest.fail(
                "_validate_log_path method does not exist; "
                "path traversal protection is missing"
            )
        except (ValueError, PermissionError):
            pass  # Expected after fix


class TestVariantAttackPaths:
    """Adjacent attack surface: symlinks and encoding variants."""

    def test_symlink_escape(self, service_with_secret):
        """A symlink inside log_dir pointing outside should be blocked."""
        service, log_dir, secret_file, _, _ = service_with_secret

        # Create a symlink inside log_dir -> secret file
        symlink_path = log_dir / "evil.log"
        try:
            symlink_path.symlink_to(secret_file)
        except OSError:
            pytest.skip("Cannot create symlinks on this platform")

        # After fix, reading a symlink that resolves outside should fail
        with pytest.raises((ValueError, FileNotFoundError, PermissionError)):
            service.read_log_file(filename="evil.log")

    def test_null_byte_injection(self, service_with_secret):
        """Filenames with null bytes should be rejected."""
        service, _, _, _, _ = service_with_secret
        with pytest.raises((ValueError, FileNotFoundError, PermissionError, OSError)):
            service.read_log_file(filename="app.log\x00../../etc/passwd")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
