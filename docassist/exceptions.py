"""All the errors this package can raise.

Everything inherits from DocAssistError, so one except clause catches the lot.
"""

from __future__ import annotations


class DocAssistError(Exception):
    """Base class for every error in this package. Never raised directly."""


class ValidationError(DocAssistError):
    """A value isn't allowed, e.g. a document with no text."""


class LoaderError(DocAssistError):
    """A file couldn't be read, or we don't know how to read that kind."""


class ProviderError(DocAssistError):
    """The AI service couldn't be reached, refused the request, or sent something odd."""
