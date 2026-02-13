class AnalysisError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class DocumentNotFoundError(AnalysisError):
    pass


class EmptyDocumentError(AnalysisError):
    pass


class AITimeoutError(AnalysisError):
    pass


class AIResponseValidationError(AnalysisError):
    def __init__(self, message: str, raw_response: str) -> None:
        self.raw_response = raw_response
        super().__init__(message)
