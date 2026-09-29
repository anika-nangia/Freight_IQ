"""Reusable async JSON fetcher with timeout, status and JSON validation."""
import logging
from typing import Any

import httpx

from app.errors import (
    ProviderError,
    ProviderHTTPError,
    ProviderInvalidResponseError,
    ProviderTimeoutError,
)

logger = logging.getLogger(__name__)


async def fetch_json(
    url: str, params: dict[str, Any], timeout: float
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params=params)
    except httpx.TimeoutException as exc:
        logger.warning("Weather provider timeout after %ss", timeout)
        raise ProviderTimeoutError("provider timed out") from exc
    except httpx.HTTPError as exc:
        logger.warning("Weather provider connection failure: %s", type(exc).__name__)
        raise ProviderError("provider unreachable") from exc

    if response.status_code >= 400:
        logger.warning("Weather provider returned HTTP %s", response.status_code)
        raise ProviderHTTPError(f"provider HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("Weather provider returned non-JSON body")
        raise ProviderInvalidResponseError("body is not JSON") from exc

    if not isinstance(data, dict):
        logger.warning("Weather provider returned unexpected JSON structure")
        raise ProviderInvalidResponseError("JSON root is not an object")
    return data
