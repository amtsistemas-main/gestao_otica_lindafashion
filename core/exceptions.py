"""Domain-level errors safe to present to end users."""


class ApplicationError(Exception):
    """Base error for expected application failures."""


class ConfigurationError(ApplicationError):
    """Raised when required application configuration is missing."""


class AuthenticationError(ApplicationError):
    """Raised when authentication cannot be completed."""
