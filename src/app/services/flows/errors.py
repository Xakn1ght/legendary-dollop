class FlowError(Exception):
    """A business-rule rejection inside a shared flow service.

    ``code`` is a stable machine-readable identifier; transports map it to an HTTP
    status + JSON error (webapp) or a localized message (bot)."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code
