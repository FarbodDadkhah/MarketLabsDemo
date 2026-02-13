from __future__ import annotations

import json

import pytest

from src.prompts.clause_extraction import validate_ai_response
from src.services.exceptions import AIResponseValidationError
from tests.conftest import VALID_AI_RESPONSE, NON_CONTRACT_RESPONSE


def test_valid_response_parses():
    result = validate_ai_response(VALID_AI_RESPONSE)
    assert result.is_contract is True
    assert len(result.clauses) == 3
    assert result.clauses[0].clause_type == "AUTO_RENEWAL"


def test_strips_markdown_fences():
    wrapped = f"```json\n{VALID_AI_RESPONSE}\n```"
    result = validate_ai_response(wrapped)
    assert len(result.clauses) == 3


def test_malformed_json_raises():
    with pytest.raises(AIResponseValidationError, match="Failed to parse AI response as JSON"):
        validate_ai_response('{"clauses": [{"clause_type":')


def test_missing_clauses_field():
    data = json.dumps({"is_contract": True, "language": "English"})
    with pytest.raises(AIResponseValidationError, match="schema validation"):
        validate_ai_response(data)


def test_invalid_risk_level():
    data = json.dumps(
        {
            "is_contract": True,
            "language": "English",
            "clauses": [
                {
                    "clause_type": "LIABILITY",
                    "risk_level": "EXTREME",
                    "title": "Bad clause",
                    "summary": "Testing invalid risk level",
                    "original_text": "Some text here",
                    "page_number": 1,
                    "confidence_score": 0.9,
                }
            ],
            "metadata": {
                "contract_type": "Test",
                "parties_involved": ["A"],
                "effective_date": None,
                "total_clauses_found": 1,
            },
        }
    )
    with pytest.raises(AIResponseValidationError, match="schema validation"):
        validate_ai_response(data)


def test_confidence_out_of_bounds():
    data = json.dumps(
        {
            "is_contract": True,
            "language": "English",
            "clauses": [
                {
                    "clause_type": "LIABILITY",
                    "risk_level": "HIGH",
                    "title": "Overbounded",
                    "summary": "Confidence too high",
                    "original_text": "Some text here",
                    "page_number": 1,
                    "confidence_score": 1.5,
                }
            ],
            "metadata": {
                "contract_type": "Test",
                "parties_involved": ["A"],
                "effective_date": None,
                "total_clauses_found": 1,
            },
        }
    )
    with pytest.raises(AIResponseValidationError, match="schema validation"):
        validate_ai_response(data)


def test_non_contract_valid():
    result = validate_ai_response(NON_CONTRACT_RESPONSE)
    assert result.is_contract is False
    assert result.clauses == []
