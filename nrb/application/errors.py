"""Safe application errors and logging for infrastructure failures."""

import logging
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger("nrb")
Result = TypeVar("Result")


class ApplicationError(RuntimeError):
    """An error with a user-safe message and optional technical cause."""


def application_error(operation: str, public_message: str, error: Exception):
    logger.error(
        "%s failed",
        operation,
        exc_info=(type(error), error, error.__traceback__),
    )
    return ApplicationError(public_message)


def log_unexpected(operation: str, error: Exception) -> None:
    logger.error(
        "%s failed",
        operation,
        exc_info=(type(error), error, error.__traceback__),
    )


def call_infrastructure(
    operation: str,
    public_message: str,
    call: Callable[..., Result],
    *args,
    **kwargs,
) -> Result:
    try:
        return call(*args, **kwargs)
    except ApplicationError:
        raise
    except Exception as error:
        raise application_error(operation, public_message, error) from error
