"""Exceptions raised by pywemo."""


class PyWeMoException(Exception):
    """Base exception class for pyWeMo exceptions."""


class ActionException(PyWeMoException):
    """Generic exceptions when dealing with SOAP request Actions."""


class SubscriptionRegistryFailed(PyWeMoException):
    """General exceptions related to the subscription registry."""


class UnknownService(PyWeMoException):
    """Exception raised when a non-existent service is called."""


class ResetException(PyWeMoException):
    """Exception raised when reset fails."""


class SetupException(PyWeMoException):
    """Exception raised when setup fails."""


class APNotFound(SetupException):
    """Exception raised when the AP requested is not found."""


class ShortPassword(SetupException):
    """Exception raised when a password is too short (<8 characters)."""


class HTTPException(PyWeMoException):
    """HTTP request to the device failed."""
