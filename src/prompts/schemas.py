from pydantic import BaseModel, Field, field_validator, model_validator

from src.models.enums import ClauseType, RiskLevel

_VALID_CLAUSE_TYPES = {member.value for member in ClauseType}
_VALID_RISK_LEVELS = {member.value for member in RiskLevel}


class ClauseExtraction(BaseModel):
    clause_type: str
    risk_level: str
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    original_text: str = Field(min_length=1)
    page_number: int | None = None
    confidence_score: float = Field(ge=0.0, le=1.0)

    @field_validator("clause_type")
    @classmethod
    def validate_clause_type(cls, v: str) -> str:
        if v not in _VALID_CLAUSE_TYPES:
            raise ValueError(
                f"Invalid clause_type '{v}'. Must be one of: {sorted(_VALID_CLAUSE_TYPES)}"
            )
        return v

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        if v not in _VALID_RISK_LEVELS:
            raise ValueError(
                f"Invalid risk_level '{v}'. Must be one of: {sorted(_VALID_RISK_LEVELS)}"
            )
        return v


class ExtractionMetadata(BaseModel):
    contract_type: str
    parties_involved: list[str]
    effective_date: str | None = None
    total_clauses_found: int = Field(ge=0)


class AIExtractionResponse(BaseModel):
    is_contract: bool
    language: str
    clauses: list[ClauseExtraction]
    metadata: ExtractionMetadata

    @model_validator(mode="after")
    def check_clauses_consistent_with_contract_flag(self) -> "AIExtractionResponse":
        if not self.is_contract and self.clauses:
            raise ValueError(
                "Document marked as non-contract but clauses were returned."
            )
        return self
