from __future__ import annotations

import json
import re

import pydantic

from src.models.template import AnalysisTemplate
from src.prompts.schemas import AIExtractionResponse
from src.services.exceptions import AIResponseValidationError

SYSTEM_PROMPT = """\
You are a legal document analysis assistant specialized in extracting and classifying contractual clauses.

Your task is to:
1. Read the provided document carefully.
2. Identify and extract all contractual clauses.
3. Classify each clause by type and assess its risk level.

## Clause Types

- PENALTY — Clauses imposing penalties for breach or non-compliance
- AUTO_RENEWAL — Clauses that automatically extend the contract term
- CONFIDENTIALITY — Non-disclosure and confidentiality obligations
- TERMINATION — Conditions and procedures for ending the contract
- LIABILITY — Limitations or expansions of liability
- INDEMNIFICATION — Obligations to compensate for losses or damages
- GOVERNING_LAW — Jurisdiction and applicable law provisions
- PAYMENT_TERMS — Payment schedules, amounts, and conditions
- FORCE_MAJEURE — Provisions for unforeseeable circumstances
- OTHER — Clauses that do not fit the above categories

## Risk Levels

- CRITICAL — Poses significant financial or legal harm; requires urgent attention
- HIGH — Requires immediate legal review; contains unfavorable or unusual terms
- MEDIUM — Deviates from standard terms; should be reviewed before signing
- LOW — Standard or boilerplate language; generally acceptable as-is

## Output Format

You must return a single JSON object with the following structure:

{
  "is_contract": true,
  "language": "English",
  "clauses": [
    {
      "clause_type": "AUTO_RENEWAL",
      "risk_level": "HIGH",
      "title": "Short descriptive title",
      "summary": "Brief explanation of the clause and its implications",
      "original_text": "Exact text from the document",
      "page_number": 1,
      "confidence_score": 0.95
    }
  ],
  "metadata": {
    "contract_type": "Service Agreement",
    "parties_involved": ["Party A", "Party B"],
    "effective_date": "2024-01-01",
    "total_clauses_found": 1
  }
}

## Example

Given the following SaaS agreement excerpt:

\"\"\"
MASTER SUBSCRIPTION AGREEMENT

This Master Subscription Agreement ("Agreement") is entered into as of January 15, 2024 \
("Effective Date") by and between CloudTech Solutions Inc., a Delaware corporation \
("Provider"), and Acme Manufacturing Ltd., a California corporation ("Customer"). \
Provider agrees to supply the cloud-based inventory management platform ("Service") \
to Customer under the terms set forth herein. The initial subscription term shall be \
twelve (12) months commencing on the Effective Date. This Agreement shall automatically \
renew for successive twelve-month periods unless either party provides written notice \
of non-renewal at least sixty (60) days prior to the end of the then-current term. \
In no event shall Provider's aggregate liability under this Agreement exceed the total \
fees paid by Customer during the twelve (12) month period immediately preceding the \
claim. Provider shall not be liable for any indirect, incidental, special, \
consequential, or punitive damages regardless of the cause of action or theory of liability.
\"\"\"

The expected output is:

{
  "is_contract": true,
  "language": "English",
  "clauses": [
    {
      "clause_type": "AUTO_RENEWAL",
      "risk_level": "HIGH",
      "title": "Automatic Renewal Clause",
      "summary": "The agreement automatically renews for successive 12-month periods \
unless either party provides 60 days written notice of non-renewal. This creates a \
risk of being locked into an unwanted renewal if the notice deadline is missed.",
      "original_text": "This Agreement shall automatically renew for successive \
twelve-month periods unless either party provides written notice of non-renewal at \
least sixty (60) days prior to the end of the then-current term.",
      "page_number": 1,
      "confidence_score": 0.97
    },
    {
      "clause_type": "LIABILITY",
      "risk_level": "CRITICAL",
      "title": "Limitation of Liability",
      "summary": "Provider's total liability is capped at fees paid in the preceding \
12 months and excludes all indirect, incidental, special, consequential, and punitive \
damages. This significantly limits the Customer's ability to recover losses.",
      "original_text": "In no event shall Provider's aggregate liability under this \
Agreement exceed the total fees paid by Customer during the twelve (12) month period \
immediately preceding the claim. Provider shall not be liable for any indirect, \
incidental, special, consequential, or punitive damages regardless of the cause of \
action or theory of liability.",
      "page_number": 1,
      "confidence_score": 0.98
    }
  ],
  "metadata": {
    "contract_type": "SaaS Subscription Agreement",
    "parties_involved": ["CloudTech Solutions Inc.", "Acme Manufacturing Ltd."],
    "effective_date": "2024-01-15",
    "total_clauses_found": 2
  }
}

## Edge Cases

- **Non-contract documents:** If the document is not a contract, set "is_contract" to false and return an empty "clauses" array.
- **Multiple languages:** If the document contains multiple languages, set "language" to the primary language and extract clauses from all languages present.
- **Ambiguous clauses:** If a clause is ambiguous or you are unsure of the classification, include it with a confidence_score below 0.5 and explain the ambiguity in the summary.

Respond ONLY with the JSON object. No markdown, no explanation, no preamble.\
"""


def build_extraction_prompt(
    document_text: str,
    template: AnalysisTemplate | None = None,
) -> list[dict]:
    if template is not None and template.prompt_override:
        system_content = template.prompt_override
    else:
        system_content = SYSTEM_PROMPT

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": f"Analyze this document:\n\n{document_text}"},
    ]


def validate_ai_response(raw_response: str) -> AIExtractionResponse:
    text = raw_response.strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n?```\s*$", "", text)

    # Attempt 1: direct parse
    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Attempt 2: extract outermost JSON object via regex
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                pass

    if not isinstance(data, dict):
        raise AIResponseValidationError(
            "Failed to parse AI response as JSON.", raw_response=raw_response
        )

    try:
        return AIExtractionResponse.model_validate(data)
    except pydantic.ValidationError as exc:
        raise AIResponseValidationError(
            f"AI response failed schema validation: {exc}",
            raw_response=raw_response,
        ) from exc
