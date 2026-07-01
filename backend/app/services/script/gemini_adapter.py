# SPDX-License-Identifier: Apache-2.0
import json

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.domain.exceptions import ScriptGenerationError
from app.services.script.interface import GeneratedScript
from app.services.script.prompts import _STRICT_ADDENDUM, build_prompt_v1

logger = structlog.get_logger(__name__)

_ARTIFACT_CHARS = frozenset({"[", "]", "•", "**"})


def _has_artifacts(text: str) -> bool:
    return any(ch in text for ch in _ARTIFACT_CHARS)


class GeminiScriptGenerator:
    """Script generator using the Gemini multimodal API (google-genai SDK)."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(httpx.TimeoutException),
        reraise=True,
    )
    async def _call_api(self, prompt: str, image_bytes: bytes) -> str:
        from google import genai  # type: ignore[import-untyped,unused-ignore]
        from google.genai import types  # type: ignore[import-untyped,unused-ignore]

        # A request timeout is mandatory: without it a stalled Gemini call hangs
        # the Celery worker indefinitely and blocks the whole cpu queue. The
        # tenacity retry above triggers on the resulting timeout. (timeout is ms.)
        client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=60_000),
        )
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        if response.text is None:
            raise ScriptGenerationError("Gemini returned an empty response")
        return response.text

    def _parse_response(self, raw: str) -> GeneratedScript:
        try:
            data = json.loads(raw)
            return GeneratedScript(
                text=str(data["text"]),
                estimated_reading_seconds=int(data["estimated_reading_seconds"]),
                pronunciation_hints=data.get("pronunciation_hints"),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ScriptGenerationError(f"Invalid LLM response schema: {exc}") from exc

    async def generate(
        self,
        slide_image_bytes: bytes,
        slide_text: str,
        style_reference: str | None,
        pronunciation_hints: str | None,
    ) -> GeneratedScript:
        prompt = build_prompt_v1(
            slide_text=slide_text,
            style_reference=style_reference,
            pronunciation_hints=pronunciation_hints,
        )

        raw = await self._call_api(prompt, slide_image_bytes)
        result = self._parse_response(raw)

        if _has_artifacts(result.text):
            logger.warning("gemini_output_has_artifacts", model=settings.gemini_model)
            strict_prompt = f"{prompt}\n\n{_STRICT_ADDENDUM}"
            raw2 = await self._call_api(strict_prompt, slide_image_bytes)
            result = self._parse_response(raw2)
            if _has_artifacts(result.text):
                raise ScriptGenerationError(f"Gemini output still contains markdown artifacts after retry: {raw2!r}")

        return result
