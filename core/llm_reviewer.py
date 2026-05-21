

from __future__ import annotations
import streamlit as st
import json
import os
import re
import time
from typing import Any

from dotenv import load_dotenv
import google.generativeai as genai
from pydantic import ValidationError

from schemas.review_schema import ReviewResponse

load_dotenv()

# constants
_DEFAULT_MODEL    = genai.GenerativeModel("gemini-2.5-flash")#"gemini-2.5-flash"
_MAX_RETRIES      = 3
_RETRY_DELAY      = 2    
_RATE_LIMIT_PAUSE = 65   
_SYSTEM_PROMPT = """\
You are a senior software engineer performing a thorough AI-assisted code review.

Your responsibilities:
1. Identify real bugs (logic errors, exception-handling gaps, off-by-one errors).
2. Flag security vulnerabilities (injection, secrets in code, insecure defaults).
3. Highlight performance bottlenecks (N+1 queries, blocking I/O, memory leaks).
4. Suggest readability and maintainability improvements.
5. Point out missing or incorrect type hints, docstrings, and error handling.

STRICT RULES:
- Return ONLY valid JSON — no markdown fences, no preamble, no trailing text.
- Every issue MUST include all required fields.
- confidence_score is 0–100 (your certainty this issue is real and meaningful).
- Be concise but precise in descriptions and suggested_fix.

JSON schema (return exactly this shape):
{
  "issues": [
    {
      "title": "Short issue title",
      "description": "Detailed explanation",
      "severity": "low | medium | high | critical",
      "confidence_score": 0,
      "category": "bug | security | performance | readability | maintainability",
      "line_number": 0,
      "suggested_fix": "Concrete fix or code snippet"
    }
  ]
}
"""


# helpers 

def _parse_retry_delay(error_str: str) -> float | None:
    """Extract retryDelay seconds from a Gemini 429 error string."""
    for pattern in (r"'retryDelay':\s*'(\d+(?:\.\d+)?)s'",
                    r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"'):
        m = re.search(pattern, error_str)
        if m:
            return float(m.group(1)) + 2  # 2 s buffer
    return None


def _is_daily_quota_exhausted(error_str: str) -> bool:
    """True for the hard daily-limit error (not retryable until midnight UTC)."""
    return "GenerateRequestsPerDayPerProject" in error_str


def _is_rate_limited(error_str: str) -> bool:
    """True for per-minute / per-second 429s (retryable after a pause)."""
    return "RESOURCE_EXHAUSTED" in error_str or "429" in error_str


# custom exceptions 

class QuotaExhaustedError(Exception):
    """Raised when the daily free-tier quota is fully consumed."""


# reviewer 

class LLMReviewer:
    """AI code-review engine powered by Google Gemini."""

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        api_key = st.secrets["GEMINI_API_KEY"].strip()
        genai.configure(api_key=api_key)

        self.client = genai.GenerativeModel(self.model_name)
       
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not found. "
                "Add it to your .env file or set it as an environment variable."
            )
        self.client       = genai.Client(api_key=api_key)
        self.model_name   = model_name
        self.quota_exhausted: bool = False

    # prompt 

    def build_prompt(self, function_name: str, source_code: str,
                     file_path: str = "") -> str:
        return (
            f"{_SYSTEM_PROMPT}\n\n"
            f"FILE: {file_path}\n"
            f"FUNCTION: {function_name}\n\n"
            f"CODE:\n```python\n{source_code}\n```"
        )

    # response cleaning 

    @staticmethod
    def _clean(text: str) -> str:
        text = text.strip()
        for fence in ("```json", "```"):
            if text.startswith(fence):
                text = text[len(fence):]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    # core review 
    def review_code(self, function_name: str, source_code: str,
                    file_path: str = "") -> dict[str, Any]:
        """
        Review a single function.

        Returns {"success": True, "data": <dict>}
             or {"success": False, "error": str, "quota_exhausted": bool}

        Raises QuotaExhaustedError when the daily limit is hit so the
        caller can abort the full scan immediately.
        """
        if self.quota_exhausted:
            raise QuotaExhaustedError("Daily quota already exhausted.")

        prompt = self.build_prompt(function_name, source_code, file_path)
        delay  = _RETRY_DELAY
        last_error = ""

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp    = self.client.models.generate_content(
                    model=self.model_name, contents=prompt
                )
                cleaned = self._clean(resp.text)
                parsed  = json.loads(cleaned)
                validated = ReviewResponse(**parsed)
                return {"success": True, "data": validated.model_dump()}

            except json.JSONDecodeError as e:
                last_error = f"JSON parse error (attempt {attempt}): {e}"

            except ValidationError as e:
                return {"success": False, "error": f"Schema validation failed: {e}",
                        "quota_exhausted": False}

            except Exception as e:
                err_str    = str(e)
                last_error = f"API error (attempt {attempt}): {err_str}"

                if _is_daily_quota_exhausted(err_str):
                    self.quota_exhausted = True
                    raise QuotaExhaustedError(
                        "Daily Gemini free-tier quota exhausted (20 req/day). "
                        "Upgrade at https://aistudio.google.com/plan_information "
                        "or wait until midnight UTC."
                    )

                if _is_rate_limited(err_str):
                    wait = _parse_retry_delay(err_str) or _RATE_LIMIT_PAUSE
                    last_error = (
                        f"Rate-limited (attempt {attempt}). "
                        f"Waiting {wait:.0f}s…"
                    )
                    if attempt < _MAX_RETRIES:
                        time.sleep(wait)
                    continue

            if attempt < _MAX_RETRIES:
                time.sleep(delay)
                delay *= 2

        return {"success": False, "error": last_error, "quota_exhausted": False}

    #batch helper

    def review_functions(self, functions: list[dict],
                         file_path: str = "") -> list[dict[str, Any]]:
        """
        Review a list of {name, code} dicts.
        Stops immediately if the daily quota is exhausted.
        """
        results = []
        for fn in functions:
            result = self.review_code(fn["name"], fn["code"], file_path)
            result["function_name"] = fn["name"]
            result["file_path"]     = file_path
            results.append(result)
        return results
