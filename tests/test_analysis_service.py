from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.enums import AnalysisStatus
from src.services.analysis_service import AnalysisService
from src.services.exceptions import (
    AITimeoutError,
    DocumentNotFoundError,
    EmptyDocumentError,
)
from tests.conftest import MALFORMED_JSON, MockAIClient, VALID_AI_RESPONSE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_document(*, extracted_text: str | None = "Some contract text") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        extracted_text=extracted_text,
    )


def _configure_session_for_document(session, document):
    """Make session.execute return a result whose scalar_one_or_none gives *document*."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = document
    session.execute = AsyncMock(return_value=mock_result)


def _configure_session_no_document(session):
    """Make session.execute return a result whose scalar_one_or_none gives None."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_analysis(mock_db_session):
    doc = _make_document()
    _configure_session_for_document(mock_db_session, doc)
    client = MockAIClient([VALID_AI_RESPONSE])

    svc = AnalysisService(client, mock_db_session)
    analysis = await svc.analyze_document(doc.id, doc.tenant_id)

    assert analysis.status == AnalysisStatus.COMPLETED
    assert analysis.completed_at is not None
    assert client.call_count == 1
    # 1 Analysis + 3 Clauses = 4 objects added
    assert len(mock_db_session.added_objects) == 4


@pytest.mark.asyncio
async def test_retry_then_success(mock_db_session):
    doc = _make_document()
    _configure_session_for_document(mock_db_session, doc)
    client = MockAIClient([
        AITimeoutError("timeout 1"),
        AITimeoutError("timeout 2"),
        VALID_AI_RESPONSE,
    ])

    svc = AnalysisService(client, mock_db_session)
    analysis = await svc.analyze_document(doc.id, doc.tenant_id)

    assert analysis.status == AnalysisStatus.COMPLETED
    assert client.call_count == 3
    assert analysis.retry_count == 2


@pytest.mark.asyncio
async def test_all_retries_exhausted(mock_db_session):
    doc = _make_document()
    _configure_session_for_document(mock_db_session, doc)
    # max_retries=3 means 3 attempts total; provide enough timeouts
    client = MockAIClient([
        AITimeoutError("timeout 1"),
        AITimeoutError("timeout 2"),
        AITimeoutError("timeout 3"),
        AITimeoutError("timeout 4"),
    ])

    svc = AnalysisService(client, mock_db_session)
    analysis = await svc.analyze_document(doc.id, doc.tenant_id)

    assert analysis.status == AnalysisStatus.TIMED_OUT
    assert "timed out" in analysis.error_message.lower() or "timeout" in analysis.error_message.lower()
    # Only the Analysis object should be added (no clauses)
    assert len(mock_db_session.added_objects) == 1


@pytest.mark.asyncio
async def test_malformed_response(mock_db_session):
    doc = _make_document()
    _configure_session_for_document(mock_db_session, doc)
    client = MockAIClient([MALFORMED_JSON])

    svc = AnalysisService(client, mock_db_session)
    analysis = await svc.analyze_document(doc.id, doc.tenant_id)

    assert analysis.status == AnalysisStatus.FAILED
    assert "AI response" in analysis.error_message or "JSON" in analysis.error_message


@pytest.mark.asyncio
async def test_empty_document(mock_db_session):
    doc = _make_document(extracted_text="")
    _configure_session_for_document(mock_db_session, doc)
    client = MockAIClient([VALID_AI_RESPONSE])

    svc = AnalysisService(client, mock_db_session)

    with pytest.raises(EmptyDocumentError):
        await svc.analyze_document(doc.id, doc.tenant_id)

    assert client.call_count == 0


@pytest.mark.asyncio
async def test_document_not_found(mock_db_session):
    _configure_session_no_document(mock_db_session)
    client = MockAIClient([VALID_AI_RESPONSE])

    svc = AnalysisService(client, mock_db_session)

    with pytest.raises(DocumentNotFoundError):
        await svc.analyze_document(uuid.uuid4(), uuid.uuid4())

    assert client.call_count == 0
