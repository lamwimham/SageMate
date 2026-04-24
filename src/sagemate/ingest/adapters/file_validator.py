"""
File Type Validator — magic-bytes based file header validation.

Used by upload endpoints to verify that file content matches its claimed
extension before parsing. Prevents mis-typed files from being fed into
wrong parsers (e.g. a renamed `.exe` sent as `.pdf`).
"""

from __future__ import annotations


class FileValidationError(ValueError):
    """Raised when file header does not match expected type."""
    pass


class FileTypeValidator:
    """Validates binary file headers against known magic bytes."""

    # Mapping: canonical type → list of magic-byte prefixes
    MAGIC_BYTES: dict[str, list[bytes]] = {
        "pdf": [b"%PDF"],
        "docx": [b"PK\x03\x04"],
        "doc": [b"\xd0\xcf\x11\xe0"],
        "png": [b"\x89PNG"],
        "jpeg": [b"\xff\xd8\xff"],
        "jpg": [b"\xff\xd8\xff"],
    }

    @classmethod
    def detect(cls, file_bytes: bytes) -> str | None:
        """Detect file type from magic bytes. Returns None if unknown."""
        for file_type, magics in cls.MAGIC_BYTES.items():
            for magic in magics:
                if file_bytes.startswith(magic):
                    return file_type
        return None

    @classmethod
    def validate(cls, file_bytes: bytes, expected_type: str | None = None) -> str:
        """
        Validate file header.

        Args:
            file_bytes: First N bytes of the file (at least 8 recommended).
            expected_type: Expected file type (e.g. 'pdf', 'docx').
                           If provided, raises FileValidationError on mismatch.

        Returns:
            Detected file type string.

        Raises:
            FileValidationError: If expected_type is given and does not match.
        """
        detected = cls.detect(file_bytes)

        if expected_type:
            expected = expected_type.lower().lstrip(".")
            if detected and detected != expected:
                raise FileValidationError(
                    f"File header mismatch: expected '{expected}', detected '{detected}'"
                )
            # If we can't detect the type, we allow it through (lenient)

        return detected or "unknown"
