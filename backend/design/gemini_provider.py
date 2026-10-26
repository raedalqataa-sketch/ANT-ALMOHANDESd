"""Gemini provider adapter for structured, review-only requirement interpretation.

This module never invokes the architectural engine or mutates a project.
"""
import json
import os
from typing import Any


def generate_gemini_json(*, prompt: str, payload: dict[str, Any],
                         schema: dict[str, Any], model: str) -> str:
    """Call Gemini and return its JSON text; validation belongs to the API layer."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=json.dumps(payload, ensure_ascii=False),
        config={
            "temperature": 0,
            "system_instruction": prompt,
            "response_mime_type": "application/json",
            "response_json_schema": schema,
        },
    )
    text = response.text
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Gemini returned an empty structured response")
    return text
