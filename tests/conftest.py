from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.ai_client import AIClient
from src.models.analysis import Analysis


# ---------------------------------------------------------------------------
# MockAIClient
# ---------------------------------------------------------------------------

class MockAIClient(AIClient):
    """AI client that pops pre-configured responses from a list."""

    def __init__(self, responses: list[str | Exception]) -> None:
        self._responses = list(responses)
        self.call_count = 0

    async def complete(self, messages: list[dict], model: str) -> str:
        self.call_count += 1
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


# ---------------------------------------------------------------------------
# Fixtures — sample data
# ---------------------------------------------------------------------------

VALID_AI_RESPONSE = json.dumps(
    {
        "is_contract": True,
        "language": "English",
        "clauses": [
            {
                "clause_type": "AUTO_RENEWAL",
                "risk_level": "HIGH",
                "title": "Auto-Renewal Clause",
                "summary": "Contract auto-renews annually.",
                "original_text": "This agreement shall automatically renew.",
                "page_number": 1,
                "confidence_score": 0.95,
            },
            {
                "clause_type": "LIABILITY",
                "risk_level": "CRITICAL",
                "title": "Limitation of Liability",
                "summary": "Provider liability is capped.",
                "original_text": "In no event shall liability exceed fees paid.",
                "page_number": 2,
                "confidence_score": 0.92,
            },
            {
                "clause_type": "TERMINATION",
                "risk_level": "MEDIUM",
                "title": "Termination for Convenience",
                "summary": "Either party may terminate with 30 days notice.",
                "original_text": "Either party may terminate upon 30 days written notice.",
                "page_number": 3,
                "confidence_score": 0.88,
            },
        ],
        "metadata": {
            "contract_type": "Service Agreement",
            "parties_involved": ["Acme Corp", "Beta LLC"],
            "effective_date": "2024-01-01",
            "total_clauses_found": 3,
        },
    }
)

NON_CONTRACT_RESPONSE = json.dumps(
    {
        "is_contract": False,
        "language": "English",
        "clauses": [],
        "metadata": {
            "contract_type": "N/A",
            "parties_involved": [],
            "effective_date": None,
            "total_clauses_found": 0,
        },
    }
)

MALFORMED_JSON = '{"clauses": [{"clause_type": "AUTO_RENEWAL"'

SAMPLE_DOCUMENT_TEXT = (
    "MASTER SERVICE AGREEMENT\n\n"
    "This Agreement is entered into between Acme Corp and Beta LLC. "
    "The contract shall automatically renew for successive 12-month periods."
)


@pytest.fixture()
def sample_document_text() -> str:
    return SAMPLE_DOCUMENT_TEXT


@pytest.fixture()
def valid_ai_response_json() -> str:
    return VALID_AI_RESPONSE


@pytest.fixture()
def malformed_json() -> str:
    return MALFORMED_JSON


@pytest.fixture()
def non_contract_response() -> str:
    return NON_CONTRACT_RESPONSE


# ---------------------------------------------------------------------------
# mock_db_session fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_db_session():
    session = AsyncMock()

    added_objects: list = []

    def _sync_add(obj):
        added_objects.append(obj)

    session.add = MagicMock(side_effect=_sync_add)
    session.added_objects = added_objects

    original_flush = session.flush

    async def _flush(*args, **kwargs):
        for obj in added_objects:
            if isinstance(obj, Analysis) and obj.id is None:
                obj.id = uuid.uuid4()

    session.flush = AsyncMock(side_effect=_flush)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    return session


# ---------------------------------------------------------------------------
# Autouse: patch asyncio.sleep so retries are instant
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _instant(*_args, **_kwargs):
        pass

    monkeypatch.setattr("asyncio.sleep", _instant)
