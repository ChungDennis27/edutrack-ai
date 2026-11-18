"""Personal note library: quota, validation, chunking, and disk storage.

Files live under ``backend/data/uploads/<user_id>/<uuid>.<ext>``. The original
filename is display-only and never used as a path. OCR is intentionally out of
scope: a scanned PDF with no extractable text is stored as ``empty``.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from app import db
from app.models import UserDocument
from app.services.retrieval_scope import PERSONAL_ORIGIN

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}
ALLOWED_SUBJECTS = {"chinese", "math", "english", "general"}

MAX_FILES = 20
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_CHUNKS_PER_FILE = 80
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120

EMPTY_NOTE = "抽唔到文字。掃描版 PDF 需要 OCR，今次未支援。"
FAILED_NOTE = "未能寫入知識庫，請刪除後再試。"
TRUNCATED_NOTE = f"只索引咗前 {MAX_CHUNKS_PER_FILE} 段，檔案其餘部分未入庫。"


class LibraryError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def check_quota(file_count: int, total_bytes: int, incoming_bytes: int) -> None:
    """Raise LibraryError when a new file would break the locked limits."""
    if incoming_bytes <= 0:
        raise LibraryError("檔案是空的")
    if incoming_bytes > MAX_FILE_BYTES:
        raise LibraryError("每個檔案上限 10MB", 413)
    if file_count >= MAX_FILES:
        raise LibraryError("已達 20 個檔案上限", 409)
    if total_bytes + incoming_bytes > MAX_TOTAL_BYTES:
        raise LibraryError("個人資料庫合計上限 50MB", 409)


def safe_display_name(filename: str | None) -> tuple[str, str]:
    """Return (display name, extension). Rejects anything that is not PDF/TXT/MD."""
    base = Path(filename or "").name.replace("\x00", "").strip()
    ext = Path(base).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise LibraryError("只接受 PDF、TXT、MD")
    stem = Path(base).stem.strip() or "untitled"
    stem = stem.replace("/", "_").replace("\\", "_")
    return f"{stem[:180]}{ext}", ext


def normalize_subject(subject: str | None) -> str:
    value = (subject or "").strip().lower()
    if value in ALLOWED_SUBJECTS:
        return value
    if not value:
        return "general"
    raise LibraryError("科目只可以係中文、數學、英文或通用")


def validate_payload(ext: str, data: bytes) -> None:
    if ext == ".pdf" and not data.startswith(b"%PDF"):
        raise LibraryError("呢個檔唔似有效 PDF")
    if ext in {".txt", ".md", ".markdown"} and b"\x00" in data:
        raise LibraryError("文字檔包含無效內容")


def quota_payload(documents: list[UserDocument]) -> dict:
    return {
        "files": len(documents),
        "file_limit": MAX_FILES,
        "bytes": sum(doc.size_bytes for doc in documents),
        "byte_limit": MAX_TOTAL_BYTES,
        "per_file_limit": MAX_FILE_BYTES,
    }


def build_user_chunks(
    text: str,
    *,
    user_id: int,
    document_id: int,
    filename: str,
    subject: str,
) -> tuple[list, bool]:
    """Chunk one upload. Returns (chunks, truncated). Metadata always has user_id."""
    from app.services.chroma_store import ChromaVectorStore, DocumentChunk
    from app.services.document_ingest import chunk_text, clean_text

    cleaned = clean_text(text)
    if len(cleaned) < 20:
        return [], False

    pieces = chunk_text(cleaned, CHUNK_SIZE, CHUNK_OVERLAP)
    truncated = len(pieces) > MAX_CHUNKS_PER_FILE
    pieces = pieces[:MAX_CHUNKS_PER_FILE]
    title = Path(filename).stem or filename
    owner = str(user_id)
    doc_key = str(document_id)
    chunks = []
    for index, piece in enumerate(pieces):
        metadata = {
            "origin": PERSONAL_ORIGIN,
            "user_id": owner,
            "document_id": doc_key,
            "subject": subject,
            "content_type": "user_note",
            "doc_title": title[:120],
            "source_file": filename[:180],
            "chunk_index": index,
            "language": "zh-HK",
        }
        body = f"【我的筆記·{title}】\n{piece}"
        chunks.append(
            DocumentChunk(
                id=ChromaVectorStore.make_id(body, metadata),
                text=body,
                metadata=metadata,
            )
        )
    return chunks, truncated


class LibraryService:
    def __init__(self, store, upload_root: str | Path):
        self.store = store
        self.upload_root = Path(upload_root)

    def list_documents(self, user_id: int) -> list[UserDocument]:
        return (
            UserDocument.query.filter_by(user_id=user_id)
            .order_by(UserDocument.created_at.desc(), UserDocument.id.desc())
            .all()
        )

    def path_for(self, doc: UserDocument) -> Path:
        root = self.upload_root.resolve()
        folder = (root / str(doc.user_id)).resolve()
        path = (folder / doc.stored_name).resolve()
        if path.parent != folder:
            raise LibraryError("檔案路徑無效", 500)
        return path

    def save_upload(
        self,
        *,
        user_id: int,
        filename: str | None,
        subject: str | None,
        data: bytes,
    ) -> UserDocument:
        display_name, ext = safe_display_name(filename)
        chosen_subject = normalize_subject(subject)
        validate_payload(ext, data)

        existing = self.list_documents(user_id)
        check_quota(len(existing), sum(doc.size_bytes for doc in existing), len(data))

        stored_name = f"{uuid.uuid4().hex}{ext}"
        doc = UserDocument(
            user_id=user_id,
            original_filename=display_name,
            stored_name=stored_name,
            subject=chosen_subject,
            size_bytes=len(data),
            status="processing",
            chunk_count=0,
        )
        path: Path | None = None
        db.session.add(doc)
        try:
            db.session.flush()
            folder = self.upload_root / str(user_id)
            folder.mkdir(parents=True, exist_ok=True)
            path = self.path_for(doc)
            path.write_bytes(data)
            self._index(doc, path)
            db.session.commit()
        except LibraryError:
            db.session.rollback()
            if path is not None and path.exists():
                path.unlink(missing_ok=True)
            raise
        except Exception:
            logger.exception("failed to store upload for user %s", user_id)
            doc_id = doc.id
            db.session.rollback()
            if path is not None and path.exists():
                path.unlink(missing_ok=True)
            if doc_id is not None:
                try:
                    self.store.delete_user_document(user_id, doc_id)
                except Exception:
                    logger.exception("failed to clean chunks after aborted upload")
            raise LibraryError("未能儲存檔案，請稍後再試", 500) from None
        return doc

    def _index(self, doc: UserDocument, path: Path) -> None:
        from app.services.document_ingest import extract_pages

        try:
            raw = "\n\n".join(text for _, text in extract_pages(path))
            chunks, truncated = build_user_chunks(
                raw,
                user_id=doc.user_id,
                document_id=doc.id,
                filename=doc.original_filename,
                subject=doc.subject,
            )
            if not chunks:
                doc.status = "empty"
                doc.chunk_count = 0
                doc.error_message = EMPTY_NOTE
                return
            self.store.upsert_user_chunks(chunks, user_id=doc.user_id)
            doc.status = "ready"
            doc.chunk_count = len(chunks)
            doc.error_message = TRUNCATED_NOTE if truncated else None
        except Exception:
            logger.exception("failed to index document %s", doc.id)
            try:
                self.store.delete_user_document(doc.user_id, doc.id)
            except Exception:
                logger.exception("failed to roll back chunks for document %s", doc.id)
            doc.status = "failed"
            doc.chunk_count = 0
            doc.error_message = FAILED_NOTE

    def delete_document(self, user_id: int, document_id: int) -> bool:
        doc = UserDocument.query.filter_by(id=document_id, user_id=user_id).first()
        if doc is None:
            return False
        self.store.delete_user_document(user_id, doc.id)
        path = self.path_for(doc)
        if path.exists():
            path.unlink()
        db.session.delete(doc)
        db.session.commit()
        return True
