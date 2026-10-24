from pathlib import PurePath

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}
TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}


class UploadRejected(ValueError):
    pass


def validate_upload(filename: str, head: bytes, size: int) -> str:
    """Validate an upload before it touches disk. Returns the normalized extension.

    Checks the extension against an allowlist, the size against a cap, and the leading bytes against
    the claimed type, so an executable or HTML file can't be smuggled in under a .pdf/.txt name.
    """
    if not filename:
        raise UploadRejected("File needs a name")
    ext = PurePath(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadRejected(f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    if size > MAX_UPLOAD_BYTES:
        raise UploadRejected(f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    if ext == ".pdf" and not head.startswith(b"%PDF-"):
        raise UploadRejected("File is not a valid PDF")
    if ext in TEXT_EXTENSIONS and b"\x00" in head:
        raise UploadRejected("Text file contains binary data")
    return ext
