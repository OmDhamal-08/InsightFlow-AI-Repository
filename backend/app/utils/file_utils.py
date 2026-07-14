"""File handling utility functions.

Provides helpers for directory management, file hashing, and
extension validation. Stub implementations — full logic in Phase 4.
"""

import hashlib
import os
from pathlib import Path

# Allowed upload extensions (expand per project requirements)
ALLOWED_EXTENSIONS: set[str] = {
    ".csv", ".xlsx", ".xls", ".json", ".parquet", ".tsv",
}


def ensure_directory_exists(directory: str | Path) -> Path:
    """Create a directory (and parents) if it does not already exist.

    Args:
        directory: Path to the directory to ensure.

    Returns:
        The resolved ``Path`` object for the directory.
    """
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_hash(file_path: str | Path, algorithm: str = "sha256") -> str:
    """Compute the SHA-256 (or other) hex-digest of a file.

    Reads the file in 8 KiB chunks to handle large files without
    excessive memory usage.

    Args:
        file_path: Path to the file to hash.
        algorithm: Hash algorithm name (default ``sha256``).

    Returns:
        Hex-encoded hash string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    # TODO Phase 4: Add async variant for large files
    h = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def get_file_extension(filename: str) -> str:
    """Extract the lowercase file extension including the leading dot.

    Args:
        filename: The original file name or path.

    Returns:
        Lowercase extension string, e.g. ``'.csv'``.
    """
    _, ext = os.path.splitext(filename)
    return ext.lower()


def validate_file_extension(
    filename: str,
    allowed: set[str] | None = None,
) -> bool:
    """Check whether a filename has an allowed extension.

    Args:
        filename: The file name to validate.
        allowed: Set of allowed extensions. Defaults to ``ALLOWED_EXTENSIONS``.

    Returns:
        True if the extension is in the allowed set, False otherwise.
    """
    # TODO Phase 4: Extend with MIME-type sniffing for extra security
    allowed = allowed or ALLOWED_EXTENSIONS
    return get_file_extension(filename) in allowed
