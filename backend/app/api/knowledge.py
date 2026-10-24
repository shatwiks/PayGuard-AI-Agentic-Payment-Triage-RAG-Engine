"""Knowledge base retrieval, document management, and grounded QA API router."""

import hashlib
import os
from typing import List, Optional
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.errors import (
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from backend.app.core.rate_limit import rate_limit
from backend.app.core.security import get_current_user, require_role
from backend.app.models.knowledge import KnowledgeDocument
from backend.app.models.user import User
from backend.app.schemas.knowledge import (
    DocumentAskRequest,
    DocumentAskResponse,
    DocumentUploadResponse,
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    UserDocumentDetail,
    UserDocumentSummary,
)
from backend.app.services.document_qa import DocumentQAService
from backend.app.services.ingestion import DocumentIngestionPipeline
from backend.app.services.retrieval import HybridRetrievalService

router = APIRouter(prefix="/knowledge", tags=["Knowledge & Policies"])


@router.post(
    "/search",
    response_model=KnowledgeSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Hybrid Knowledge Search",
    description="Searches authoritative payment policies and authorized documents using combined lexical and pgvector retrieval.",
)
async def search_knowledge_documents(
    request: KnowledgeSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rate_guard: None = Depends(rate_limit("knowledge_search", max_requests=settings.RATE_LIMIT_SEARCH_PER_MINUTE)),
) -> KnowledgeSearchResponse:
    """Executes hybrid, lexical-only, or semantic-only search over authorized document chunks."""
    retrieval_service = HybridRetrievalService(session=db)
    return await retrieval_service.search(request, user_id=current_user.id, user_role=current_user.role)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Compliance or Policy Document",
    description="Uploads a PDF or TXT document, parses structure, creates hierarchical chunks, and indexes for retrieval.",
)
async def upload_document(
    response: Response,
    file: UploadFile = File(..., description="PDF or TXT document file"),
    title: Optional[str] = Form(None, description="Optional custom document title"),
    doc_type: str = Form("user_upload", description="Document type tag"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rate_guard: None = Depends(rate_limit("knowledge_upload", max_requests=settings.RATE_LIMIT_UPLOAD_PER_MINUTE)),
) -> DocumentUploadResponse:
    """Handles multipart document upload with validation, safe storage, and hierarchical indexing."""
    filename = file.filename or "uploaded_document.txt"
    file_bytes = await file.read()

    pipeline = DocumentIngestionPipeline(session=db)
    res = await pipeline.ingest_user_uploaded_file(
        file_bytes=file_bytes,
        filename=filename,
        user_id=current_user.id,
        doc_type=doc_type,
        title=title,
        mime_type=file.content_type,
    )

    is_duplicate = res.status == "skipped_unchanged"
    if is_duplicate:
        response.status_code = status.HTTP_200_OK

    doc = res.document

    return DocumentUploadResponse(
        document_id=res.document_id,
        id=res.document_id,
        title=res.title,
        file_name=doc.file_name if doc else filename,
        file_size_bytes=doc.file_size_bytes if doc and doc.file_size_bytes else len(file_bytes),
        chunks_created=res.chunks_count,
        chunk_count=res.chunks_count,
        page_count=doc.page_count if doc else 1,
        processing_status=doc.processing_status if doc else "processed",
        embedding_status=doc.embedding_status if doc else "lexical_only",
        is_duplicate=is_duplicate,
        message=res.message,
    )


@router.get(
    "/documents",
    response_model=List[UserDocumentSummary],
    status_code=status.HTTP_200_OK,
    summary="List Authorized Documents",
    description="Retrieves a list of documents the current user is authorized to access.",
)
async def list_documents(
    scope: str = Query("uploaded", description="Scope: 'uploaded', 'knowledge_base', or 'all'"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[UserDocumentSummary]:
    """Lists authorized documents filtered by user ownership and system availability."""
    stmt = select(KnowledgeDocument).where(KnowledgeDocument.is_active.is_(True))

    if scope == "uploaded":
        stmt = stmt.where(
            KnowledgeDocument.uploaded_by_id == current_user.id,
            KnowledgeDocument.is_system.is_(False),
        )
    elif scope == "knowledge_base":
        stmt = stmt.where(KnowledgeDocument.is_system.is_(True))
    else:
        # "all"
        if current_user.role == "admin":
            pass  # Admin sees all
        else:
            stmt = stmt.where(
                or_(
                    KnowledgeDocument.is_system.is_(True),
                    KnowledgeDocument.uploaded_by_id == current_user.id,
                )
            )

    stmt = stmt.order_by(KnowledgeDocument.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    res = await db.execute(stmt)
    docs = res.scalars().all()
    return [UserDocumentSummary.model_validate(d) for d in docs]


@router.get(
    "/documents/{document_id}",
    response_model=UserDocumentDetail,
    status_code=status.HTTP_200_OK,
    summary="Get Document Details",
    description="Retrieves document metadata, processing status, and content preview subject to authorization.",
)
async def get_document_details(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserDocumentDetail:
    """Retrieves single document details if the user is authorized."""
    stmt = select(KnowledgeDocument).where(
        KnowledgeDocument.id == document_id,
        KnowledgeDocument.is_active.is_(True),
    )
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()

    if not doc:
        raise NotFoundException(f"Document '{document_id}' not found.")

    # Authorization guard: owner, system, or admin
    if not doc.is_system and doc.uploaded_by_id != current_user.id and current_user.role != "admin":
        raise NotFoundException(f"Document '{document_id}' not found.")

    preview = (doc.raw_content[:500] + "...") if doc.raw_content and len(doc.raw_content) > 500 else doc.raw_content

    return UserDocumentDetail(
        id=doc.id,
        title=doc.title,
        file_name=doc.file_name,
        file_size_bytes=doc.file_size_bytes,
        mime_type=doc.mime_type,
        doc_type=doc.doc_type,
        version=doc.version,
        content_hash=doc.content_hash,
        is_system=doc.is_system,
        processing_status=doc.processing_status,
        embedding_status=doc.embedding_status,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        uploaded_by_id=doc.uploaded_by_id,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        error_message=doc.error_message,
        raw_content_preview=preview,
    )


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Document",
    description="Deletes an uploaded document and cascades deletion to all associated chunks and vectors.",
)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Deletes authorized document and cleans up associated file storage."""
    stmt = select(KnowledgeDocument).where(
        KnowledgeDocument.id == document_id,
        KnowledgeDocument.is_active.is_(True),
    ).options(selectinload(KnowledgeDocument.chunks))
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()

    if not doc:
        raise NotFoundException(f"Document '{document_id}' not found.")

    if doc.is_system and current_user.role != "admin":
        raise ForbiddenException("Authoritative system documents can only be deleted by an administrator.")

    if not doc.is_system and doc.uploaded_by_id != current_user.id and current_user.role != "admin":
        raise NotFoundException(f"Document '{document_id}' not found.")

    # Remove storage file if exists
    if doc.storage_path and os.path.exists(doc.storage_path):
        try:
            os.remove(doc.storage_path)
        except Exception:
            pass

    # Soft-delete or hard delete
    await db.delete(doc)
    await db.commit()

    return {"success": True, "message": f"Document '{doc.title}' deleted successfully."}


@router.post(
    "/ask",
    response_model=DocumentAskResponse,
    status_code=status.HTTP_200_OK,
    summary="Document-Grounded Question Answering",
    description="Answers questions strictly grounded in authorized user-uploaded or system policy documents.",
)
async def ask_document_question(
    request: DocumentAskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rate_guard: None = Depends(rate_limit("knowledge_ask", max_requests=settings.RATE_LIMIT_SEARCH_PER_MINUTE)),
) -> DocumentAskResponse:
    """Answers user question strictly using evidence from authorized document chunks."""
    qa_service = DocumentQAService(session=db)
    return await qa_service.ask_question(user=current_user, request=request)


@router.post(
    "/ingest",
    response_model=KnowledgeIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest Policy Document",
    description="Admin/Compliance restricted endpoint to ingest, normalize, chunk, and embed official payment policies.",
)
async def ingest_policy_document(
    request: KnowledgeIngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "compliance_analyst"])),
    _rate_guard: None = Depends(rate_limit("knowledge_ingest", max_requests=10)),
) -> KnowledgeIngestResponse:
    """Ingests official document and persists normalized chunks with embeddings."""
    pipeline = DocumentIngestionPipeline(session=db)
    result = await pipeline.ingest_document(
        title=request.title,
        content=request.raw_content,
        source_id=request.source_id,
        doc_type=request.document_type,
        version=request.version,
        source_url=request.source_url,
        hierarchical=request.hierarchical,
    )
    content_hash = (
        result.document.content_hash
        if result.document
        else hashlib.sha256(request.raw_content.encode("utf-8")).hexdigest()
    )
    return KnowledgeIngestResponse(
        document_id=result.document_id,
        source_id=result.source_id,
        title=result.title,
        chunks_created=result.chunks_count,
        content_hash=content_hash,
        status="ingested",
    )
