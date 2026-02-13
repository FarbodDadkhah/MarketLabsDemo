import enum


class FileType(str, enum.Enum):
    PDF = "PDF"
    DOCX = "DOCX"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"


class AnalysisStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class ClauseType(str, enum.Enum):
    PENALTY = "PENALTY"
    AUTO_RENEWAL = "AUTO_RENEWAL"
    CONFIDENTIALITY = "CONFIDENTIALITY"
    TERMINATION = "TERMINATION"
    LIABILITY = "LIABILITY"
    INDEMNIFICATION = "INDEMNIFICATION"
    GOVERNING_LAW = "GOVERNING_LAW"
    PAYMENT_TERMS = "PAYMENT_TERMS"
    FORCE_MAJEURE = "FORCE_MAJEURE"
    OTHER = "OTHER"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
