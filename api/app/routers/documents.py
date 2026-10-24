import uuid
from pathlib import Path, PurePosixPath
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.container import get_job_queue, get_url_guard, get_vector_store
from app.core.config import get_settings
from app.db.models import Bot, Document
from app.db.session import get_db
from app.ingest.url_safety import UnsafeUrl
from app.ingest.validation import MAX_UPLOAD_BYTES, UploadRejected, validate_upload
from app.rag.vectorstores.base import VectorStore, namespace_for
from app.repositories.documents import DocumentRepository
from app.routers.deps import owned_bot
from app.schemas import DocumentOut, UrlIngest

router = APIRouter(prefix="/bots/{bot_id}/documents", tags=["documents"])
READ_CHUNK = 1024 * 1024


def _safe_display_name(filename: str) -> str:
    # Only ever used as a label. Files are stored under a random UUID name, so a name like
    # "../../etc/passwd" can't escape the storage directory.
    return PurePosixPath(filename.replace("\\", "/")).name[:200] or "upload"


@router.get("", response_model=list[DocumentOut])
def list_documents(bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    return DocumentRepository(db).list_for_bot(bot.id)


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload(
    file: UploadFile,
    bot: Bot = Depends(owned_bot),
    db: Session = Depends(get_db),
    queue=Depends(get_job_queue),
):
    # Read in 1 MB pieces and stop at the cap. Content-Length is client-controlled, so don't trust it.
    head = await file.read(READ_CHUNK)
    data = bytearray(head)
    while piece := await file.read(READ_CHUNK):
        data.extend(piece)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File too large")
    try:
        ext = validate_upload(file.filename or "", bytes(head[:1024]), len(data))
    except UploadRejected as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    storage: Path = get_settings().storage_dir
    storage.mkdir(parents=True, exist_ok=True)
    path = storage / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(data)

    doc = DocumentRepository(db).add(
        Document(bot_id=bot.id, title=_safe_display_name(file.filename or ""), source_type="file",
                 file_path=str(path), status="queued")
    )
    db.commit()
    await queue.enqueue_ingest(doc.id)
    return doc


@router.post("/url", status_code=status.HTTP_202_ACCEPTED)
async def add_url(
    body: UrlIngest,
    bot: Bot = Depends(owned_bot),
    db: Session = Depends(get_db),
    queue=Depends(get_job_queue),
    url_guard=Depends(get_url_guard),
):
    url = str(body.url)
    try:
        url_guard(url)  # fail fast here; the crawler re-checks every hop and redirect
    except UnsafeUrl as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    if body.crawl:
        max_pages = body.max_pages or get_settings().crawl_max_pages
        await queue.enqueue_crawl(bot.id, url, max_pages)
        return {"status": "crawling", "url": url, "max_pages": max_pages}

    doc = DocumentRepository(db).add(
        Document(bot_id=bot.id, title=url, source_type="url", source_url=url, status="queued")
    )
    db.commit()
    await queue.enqueue_ingest(doc.id)
    return DocumentOut.model_validate(doc)


@router.post("/{document_id}/reindex", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def reindex(
    document_id: UUID,
    bot: Bot = Depends(owned_bot),
    db: Session = Depends(get_db),
    queue=Depends(get_job_queue),
):
    doc = DocumentRepository(db).get_for_bot(bot.id, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    doc.status, doc.error = "queued", None
    db.commit()
    await queue.enqueue_ingest(doc.id)
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    bot: Bot = Depends(owned_bot),
    db: Session = Depends(get_db),
    store: VectorStore = Depends(get_vector_store),
):
    repo = DocumentRepository(db)
    doc = repo.get_for_bot(bot.id, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    store.delete_document(namespace_for(bot.id), str(doc.id))
    file_path = doc.file_path
    repo.delete(doc)
    db.commit()
    if file_path:
        Path(file_path).unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
