# SPDX-License-Identifier: Apache-2.0
import base64
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


class OllamaScriptGenerator:
    """Script generator using a local Ollama multimodal API (qwen2.5-vl:7b by default)."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(httpx.TimeoutException),
        reraise=True,
    )
    async def _call_api(self, prompt: str, image_bytes: bytes) -> str:
        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "images": [base64.b64encode(image_bytes).decode()],
            "stream": False,
            "format": "json",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
        raw: str = response.json().get("response", "")
        if not raw:
            raise ScriptGenerationError("Ollama returned an empty response")
        return raw

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
            logger.warning("ollama_output_has_artifacts", model=settings.ollama_model)
            strict_prompt = f"{prompt}\n\n{_STRICT_ADDENDUM}"
            raw2 = await self._call_api(strict_prompt, slide_image_bytes)
            result = self._parse_response(raw2)
            if _has_artifacts(result.text):
                raise ScriptGenerationError(
                    f"Ollama output still contains markdown artifacts after retry: {raw2!r}"
                )

        return result
