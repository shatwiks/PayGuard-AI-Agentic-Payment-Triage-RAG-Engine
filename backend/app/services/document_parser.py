"""Secure document parsing service for user-uploaded compliance and policy files.

Supports:
1. Native PDF text extraction with page preservation via pypdf.
2. UTF-8 and fallback encoded plain text files (.txt).
3. Magic byte and header format validation (prevents extension spoofing).
4. Detection of empty, corrupted, unreadable, or binary files.
5. Cryptographic SHA-256 content hashing.
"""

from dataclasses import dataclass, field
import hashlib
import io
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import pypdf
from pypdf.errors import PdfReadError

from backend.app.core.config import settings
from backend.app.core.errors import PayGuardException

logger = logging.getLogger(__name__)


class DocumentParsingException(PayGuardException):
    """Base exception for document parsing failures."""
    def __init__(self, message: str, code: str = "DOCUMENT_PARSE_ERROR", status_code: int = 400):
        super().__init__(message=message, code=code, status_code=status_code)


class EmptyDocumentException(DocumentParsingException):
    """Raised when uploaded file contains zero bytes or only whitespace."""
    def __init__(self, message: str = "Uploaded document is empty or contains only whitespace."):
        super().__init__(message=message, code="EMPTY_DOCUMENT", status_code=400)


class CorruptedDocumentException(DocumentParsingException):
    """Raised when PDF structure is corrupted or unparseable."""
    def __init__(self, message: str = "Document file is corrupted and cannot be read."):
        super().__init__(message=message, code="CORRUPTED_DOCUMENT", status_code=422)


class UnreadableDocumentException(DocumentParsingException):
    """Raised when PDF contains no extractable text (e.g. image-only or scanned)."""
    def __init__(self, message: str = "PDF contains no extractable text. Scanned or image-only documents require OCR."):
        super().__init__(message=message, code="UNREADABLE_DOCUMENT", status_code=422)


class UnsupportedDocumentTypeException(DocumentParsingException):
    """Raised when file extension or MIME type is not allowed."""
    def __init__(self, message: str = "Unsupported document type. Only PDF (.pdf) and TXT (.txt) files are supported."):
        super().__init__(message=message, code="UNSUPPORTED_DOCUMENT_TYPE", status_code=415)


class DocumentSizeLimitException(DocumentParsingException):
    """Raised when file exceeds maximum allowed upload size."""
    def __init__(self, message: str = "Document exceeds maximum upload size limit."):
        super().__init__(message=message, code="DOCUMENT_TOO_LARGE", status_code=413)


@dataclass
class ParsedDocument:
    """Standardized output of the document parser."""
    raw_content: str
    page_count: int
    pages: List[Tuple[int, str]]  # 1-indexed (page_number, text)
    content_hash: str
    file_name: str
    file_size_bytes: int
    mime_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentParser:
    """Validates, sanitizes, and extracts text and structure from uploaded documents."""

    PDF_MAGIC = b"%PDF-"

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Strips path traversal sequences and dangerous characters from filenames."""
        clean = os.path.basename(filename or "document.txt")
        # Keep alphanumeric, dot, hyphen, underscore, and space
        clean = re.sub(r"[^\w\.\-\s]", "_", clean).strip()
        return clean or "document.txt"

    def parse(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: Optional[str] = None,
    ) -> ParsedDocument:
        """Parses document bytes, extracting text and structural metadata."""
        if not file_bytes:
            raise EmptyDocumentException("Uploaded file contains zero bytes.")

        file_size = len(file_bytes)
        if file_size > settings.UPLOAD_MAX_FILE_SIZE_BYTES:
            raise DocumentSizeLimitException(
                f"File size ({file_size} bytes) exceeds limit of {settings.UPLOAD_MAX_FILE_SIZE_BYTES} bytes."
            )

        safe_filename = self.sanitize_filename(filename)
        ext = os.path.splitext(safe_filename)[1].lower()

        if ext not in settings.UPLOAD_ALLOWED_EXTENSIONS:
            raise UnsupportedDocumentTypeException(
                f"File extension '{ext}' is not supported. Allowed formats: {settings.UPLOAD_ALLOWED_EXTENSIONS}"
            )

        content_hash = hashlib.sha256(file_bytes).hexdigest()

        if ext == ".pdf":
            return self._parse_pdf(file_bytes, safe_filename, file_size, content_hash, mime_type)
        elif ext == ".txt":
            return self._parse_txt(file_bytes, safe_filename, file_size, content_hash, mime_type)
        else:
            raise UnsupportedDocumentTypeException(f"Unsupported format: {ext}")

    def _parse_pdf(
        self,
        file_bytes: bytes,
        filename: str,
        file_size: int,
        content_hash: str,
        mime_type: Optional[str],
    ) -> ParsedDocument:
        """Parses PDF document and extracts text page by page."""
        # Magic bytes verification
        if not file_bytes.startswith(self.PDF_MAGIC):
            # Check within first 1024 bytes (some PDFs have leading whitespace/comments)
            if self.PDF_MAGIC not in file_bytes[:1024]:
                raise CorruptedDocumentException("File does not start with valid PDF header magic bytes.")

        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        except (PdfReadError, Exception) as exc:
            logger.warning("PDF reader failed on %s: %s", filename, exc)
            raise CorruptedDocumentException(f"Failed to read PDF document structure: {str(exc)}")

        if reader.is_encrypted:
            try:
                # Attempt empty password decryption
                decrypted = reader.decrypt("")
                if not decrypted:
                    raise CorruptedDocumentException("Encrypted/password-protected PDFs are not supported.")
            except Exception:
                raise CorruptedDocumentException("Encrypted/password-protected PDFs are not supported.")

        pages: List[Tuple[int, str]] = []
        total_text_parts: List[str] = []

        try:
            for page_idx, page in enumerate(reader.pages):
                page_num = page_idx + 1
                try:
                    text = page.extract_text() or ""
                except Exception as extract_err:
                    logger.warning("Text extraction failed on page %d of %s: %s", page_num, filename, extract_err)
                    text = ""

                clean_text = text.strip()
                pages.append((page_num, clean_text))
                if clean_text:
                    total_text_parts.append(clean_text)
        except Exception as exc:
            raise CorruptedDocumentException(f"Error extracting pages from PDF: {str(exc)}")

        full_content = "\n\n".join(total_text_parts).strip()
        if not full_content:
            raise UnreadableDocumentException(
                "PDF contains no extractable text. Scanned or image-only documents require OCR."
            )

        return ParsedDocument(
            raw_content=full_content,
            page_count=len(reader.pages),
            pages=pages,
            content_hash=content_hash,
            file_name=filename,
            file_size_bytes=file_size,
            mime_type=mime_type or "application/pdf",
            metadata={
                "pdf_version": reader.pdf_header if hasattr(reader, "pdf_header") else None,
                "title": reader.metadata.title if reader.metadata and reader.metadata.title else None,
                "author": reader.metadata.author if reader.metadata and reader.metadata.author else None,
            },
        )

    def _parse_txt(
        self,
        file_bytes: bytes,
        filename: str,
        file_size: int,
        content_hash: str,
        mime_type: Optional[str],
    ) -> ParsedDocument:
        """Parses plain text document with robust encoding fallback."""
        # Check for null bytes to reject binary disguised as text
        if b"\x00" in file_bytes:
            raise UnsupportedDocumentTypeException("File contains binary null bytes and cannot be parsed as text.")

        text: Optional[str] = None
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                text = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if text is None:
            raise CorruptedDocumentException("Failed to decode text file using UTF-8 or compatible encodings.")

        clean_text = text.strip()
        if not clean_text:
            raise EmptyDocumentException("Text document contains only whitespace.")

        return ParsedDocument(
            raw_content=clean_text,
            page_count=1,
            pages=[(1, clean_text)],
            content_hash=content_hash,
            file_name=filename,
            file_size_bytes=file_size,
            mime_type=mime_type or "text/plain",
            metadata={},
        )
