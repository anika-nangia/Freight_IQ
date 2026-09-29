"""Domain exceptions. None of these are ever serialised with a stack trace."""


class ProviderError(Exception):
    """Weather provider could not deliver usable data."""

    public_message = "Weather data is temporarily unavailable."


class ProviderTimeoutError(ProviderError):
    pass


class ProviderHTTPError(ProviderError):
    pass


class ProviderInvalidResponseError(ProviderError):
    pass


class PortNotFoundError(Exception):
    def __init__(self, port_name: str) -> None:
        self.port_name = port_name
        super().__init__(f"Unsupported port: {port_name}")


class AppError(Exception):
    """Base for errors that map to a clean JSON error response."""

    status_code = 400
    code = "ERROR"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class SeriesNotFoundError(AppError):
    status_code = 404
    code = "SERIES_NOT_AVAILABLE"


class DatasetError(AppError):
    status_code = 503
    code = "DATASET_UNAVAILABLE"


class InvalidParameterError(AppError):
    status_code = 422
    code = "INVALID_PARAMETER"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
