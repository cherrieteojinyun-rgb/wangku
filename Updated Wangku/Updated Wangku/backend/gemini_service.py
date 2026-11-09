"""Compatibility shim: server imports gemini_service. Reuse gemini_coach implementation."""

from gemini_coach import SYSTEM, CoachError, _request  # noqa: F401
