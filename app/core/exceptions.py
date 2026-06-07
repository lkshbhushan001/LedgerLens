"""Centralised exception hierarchy for domain and HTTP errors."""


class AppException(Exception):
    """Base application exception with HTTP-aware metadata."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class AuthenticationError(AppException):
    def __init__(self, detail: str = "Authentication failed") -> None:
        super().__init__(401, detail)


class AuthorizationError(AppException):
    def __init__(self, detail: str = "Insufficient permissions") -> None:
        super().__init__(403, detail)


class DocumentNotFoundError(AppException):
    def __init__(self, detail: str = "Document not found") -> None:
        super().__init__(404, detail)


class IngestionError(AppException):
    def __init__(self, detail: str = "Document ingestion failed") -> None:
        super().__init__(422, detail)


class VectorStoreError(AppException):
    def __init__(self, detail: str = "Vector store operation failed") -> None:
        super().__init__(503, detail)
