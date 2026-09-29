"""
Every error leaves the API as `{"error": "<message for the customer>", "field": "<input path>"?}`
with a fitting status code, so the frontend can show it inline next to the right control.
"""

import logging

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

log = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, message: str, status_code: int = 400, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.field = field


def _first_error(detail, path=""):
    """Walk DRF's nested error detail and return (message, field path) of the first problem."""
    if isinstance(detail, dict):
        for key, value in detail.items():
            sub = path if key == "non_field_errors" else (f"{path}.{key}" if path else str(key))
            found = _first_error(value, sub)
            if found:
                return found
        return None
    if isinstance(detail, list):
        for item in detail:
            found = _first_error(item, path)
            if found:
                return found
        return None
    return str(detail), (path or None)


def _payload(message, field=None):
    body = {"error": message}
    if field:
        body["field"] = field
    return body


def exception_handler(exc, context):
    if isinstance(exc, ApiError):
        return Response(_payload(exc.message, exc.field), status=exc.status_code)
    if isinstance(exc, ValidationError):
        found = _first_error(exc.detail) or ("Invalid request", None)
        return Response(_payload(*found), status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        return Response(_payload("Please sign in first"), status=status.HTTP_401_UNAUTHORIZED)
    if isinstance(exc, PermissionDenied):
        return Response(_payload(str(exc.detail)), status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, (NotFound, Http404)):
        return Response(_payload("Not found"), status=status.HTTP_404_NOT_FOUND)

    response = drf_exception_handler(exc, context)
    if response is not None:
        detail = response.data.get("detail") if isinstance(response.data, dict) else None
        return Response(_payload(str(detail or "Request failed")), status=response.status_code)

    log.exception("Unhandled error in %s", context.get("view"))
    return Response(_payload("Something went wrong. Please try again."), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
