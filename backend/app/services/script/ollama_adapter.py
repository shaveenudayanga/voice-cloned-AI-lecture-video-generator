# SPDX-License-Identifier: Apache-2.0
import base64
import json

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.domain.exceptions import ScriptGenerationError
from app.services.script.interface import GeneratedScript
from app.services.script.prompts import SLIDE_BLOCK, STYLE_REFERENCE_BLOCK, SYSTEM_PROMPT_V1

logger = structlog.get_logger(__name__)


class OllamaScriptGenerator:
    """Script generator using local Ollama multimodal API (qwen2.5-vl:7b by default)."""

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate(
        self,
        slide_image_png: bytes,
        slide_text: str,
        style_reference_transcript: str,
        extra_style_sample: str | None = None,
    ) -> GeneratedScript:
        style_block = STYLE_REFERENCE_BLOCK.format(transcript=style_reference_transcript)
        if extra_style_sample:
            style_block += f"\n\nAdditional style sample:\n{extra_style_sample}"

        prompt = "\n\n".join([
            SYSTEM_PROMPT_V1,
            style_block,
            SLIDE_BLOCK.format(slide_text=slide_text),
            "Generate the narration script as specified.",
        ])

        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "images": [base64.b64encode(slide_image_png).decode()],
            "stream": False,
            "format": "json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            raw = response.json().get("response", "")

        return self._parse_response(raw)

    def _parse_response(self, raw: str) -> GeneratedScript:
        try:
            data = json.loads(raw)
            return GeneratedScript(
                narration_text=str(data["narration_text"]),
                estimated_reading_time_s=float(data["estimated_reading_time_s"]),
                pronunciation_hints=data.get("pronunciation_hints"),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ScriptGenerationError(f"Invalid LLM response schema: {exc}") from exc
