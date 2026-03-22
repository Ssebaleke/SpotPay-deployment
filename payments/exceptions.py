"""
payments/exceptions.py
Yo! Payments custom exceptions.
"""


class YoPaymentsError(Exception):
    """
    Raised when:
      - Yo! API returns Status=ERROR
      - All endpoints fail (network / timeout)
      - XML response cannot be parsed
    """

    def __init__(self, message: str, code: str = None, raw: str = None):
        super().__init__(message)
        self.code = code   # ErrorMessageCode from Yo! response
        self.raw = raw     # raw XML string for debugging


class YoNetworkError(YoPaymentsError):
    """All configured endpoints failed (timeout / connection error)."""


class YoValidationError(YoPaymentsError):
    """Invalid input before a request is even sent (e.g. bad phone number)."""
