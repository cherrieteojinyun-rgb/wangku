"""Shared chat transport for Wangku apps. No API keys stored here."""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_MODEL = "gemini-flash-latest"


class ChatTransportError(Exception):
    """Transport-level error with a user-facing message."""


def validate_https_base(url):
    parsed = urllib.parse.urlparse((url or "").strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    return True


def post_backend(contents, url, token, *, context=None, timeout=50):
    if not validate_https_base(url):
        raise ChatTransportError("invalid_url")
    if not (token or "").strip():
        raise ChatTransportError("missing_token")
    payload = {"context": context or {}, "contents": contents}
    request = urllib.request.Request(
        url.rstrip("/") + "/coach",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token.strip()},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise ChatTransportError("unauthorized") from None
        if error.code == 429:
            raise ChatTransportError("rate_limit") from None
        if error.code in (502, 503, 504):
            raise ChatTransportError("unavailable") from None
        raise ChatTransportError("request_failed") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ChatTransportError("network") from None
    except (ValueError, TypeError):
        raise ChatTransportError("bad_response") from None
    reply = result.get("reply") if isinstance(result, dict) else None
    if not isinstance(reply, str) or not reply.strip():
        raise ChatTransportError("empty")
    return reply.strip()


def post_gemini(contents, *, system_instruction, model=None, timeout=50):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise ChatTransportError("missing_key")
    model = (model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)).strip() or DEFAULT_MODEL
    if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
        raise ChatTransportError("invalid_model")
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 1200, "temperature": 0.4},
    }
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise ChatTransportError("rate_limit") from None
        if error.code in (400, 401, 403):
            raise ChatTransportError("unauthorized") from None
        raise ChatTransportError("request_failed") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ChatTransportError("network") from None
    except (ValueError, TypeError):
        raise ChatTransportError("bad_response") from None
    candidates = result.get("candidates") or []
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    text = "\n".join(part.get("text", "") for part in parts if not part.get("thought")).strip()
    if not text:
        raise ChatTransportError("empty")
    return text
