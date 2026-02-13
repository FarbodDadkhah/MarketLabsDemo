from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.analysis import Analysis
from src.models.clause import Clause
from src.models.document import Document
from src.models.enums import AnalysisStatus, ClauseType, RiskLevel
from src.models.template import AnalysisTemplate
from src.prompts.clause_extraction import build_extraction_prompt, validate_ai_response
from src.services.ai_client import AIClient
from src.services.exceptions import (
    AIResponseValidationError,
    AITimeoutError,
    DocumentNotFoundError,
    EmptyDocumentError,
)
from src.services.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self, ai_client: AIClient, db_session: AsyncSession) -> None:
        self._ai = ai_client
        self._db = db_session

    async def analyze_document(
        self,
        document_id: object,
        tenant_id: object,
        template_id: object | None = None,
        model_provider: str = "anthropic",
        model_name: str = "claude-sonnet-4-5-20250514",
    ) -> Analysis:
        # 1. Fetch document with tenant isolation
        result = await self._db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.tenant_id == tenant_id,
            )
        )
        document = result.scalar_one_or_none()
        if document is None:
            raise DocumentNotFoundError(
                f"Document {document_id} not found for tenant {tenant_id}"
            )

        # 2. Validate extracted text
        if not document.extracted_text:
            raise EmptyDocumentError(
                f"Document {document_id} has no extracted text"
            )

        # 3. Fetch template (optional)
        template: AnalysisTemplate | None = None
        if template_id is not None:
            tmpl_result = await self._db.execute(
                select(AnalysisTemplate).where(
                    AnalysisTemplate.id == template_id,
                    AnalysisTemplate.tenant_id == tenant_id,
                )
            )
            template = tmpl_result.scalar_one_or_none()
            if template is None:
                logger.warning(
                    "Template %s not found for tenant %s; proceeding without template",
                    template_id,
                    tenant_id,
                )

        # 4. Create Analysis record
        analysis = Analysis(
            document_id=document.id,
            tenant_id=document.tenant_id,
            template_id=template.id if template else None,
            status=AnalysisStatus.PROCESSING,
            model_provider=model_provider,
            model_name=model_name,
            started_at=datetime.now(timezone.utc),
        )
        self._db.add(analysis)
        await self._db.flush()

        # 5. AI call
        attempt_counter = [0]

        async def _call_ai() -> str:
            attempt_counter[0] += 1
            messages = build_extraction_prompt(document.extracted_text, template)
            return await self._ai.complete(messages, model_name)

        try:
            raw_response = await retry_with_backoff(_call_ai, max_retries=3)
            validated = validate_ai_response(raw_response)

            for clause_data in validated.clauses:
                clause = Clause(
                    analysis_id=analysis.id,
                    clause_type=ClauseType(clause_data.clause_type),
                    risk_level=RiskLevel(clause_data.risk_level),
                    title=clause_data.title,
                    summary=clause_data.summary,
                    original_text=clause_data.original_text,
                    page_number=clause_data.page_number,
                    confidence_score=clause_data.confidence_score,
                )
                self._db.add(clause)

            analysis.status = AnalysisStatus.COMPLETED
            analysis.completed_at = datetime.now(timezone.utc)

        except AITimeoutError as exc:
            analysis.status = AnalysisStatus.TIMED_OUT
            analysis.error_message = str(exc)

        except AIResponseValidationError as exc:
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(exc)

        except Exception as exc:
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(exc)
            logger.exception("Unexpected error during analysis of document %s", document_id)

        finally:
            analysis.retry_count = max(attempt_counter[0] - 1, 0)
            await self._db.commit()

        # 6. Return refreshed analysis
        await self._db.refresh(analysis)
        return analysis
