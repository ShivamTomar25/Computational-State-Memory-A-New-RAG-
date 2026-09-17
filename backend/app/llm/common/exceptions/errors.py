from __future__ import annotations


class LlmError(Exception):
    pass


class LlmNotConfigured(LlmError):
    pass


class LlmProviderUnavailable(LlmError):
    pass


class LlmAuthenticationFailed(LlmError):
    pass


class LlmRateLimited(LlmError):
    pass


class LlmTimeout(LlmError):
    pass


class LlmInvalidModel(LlmError):
    pass


class LlmContextTooLarge(LlmError):
    pass


class LlmStructuredOutputFailed(LlmError):
    pass


class LlmCitationValidationFailed(LlmError):
    pass


class LlmDataEgressBlocked(LlmError):
    pass


class LlmCircuitOpen(LlmError):
    pass
