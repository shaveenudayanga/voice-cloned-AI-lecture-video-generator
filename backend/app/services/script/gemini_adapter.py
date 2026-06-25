# SPDX-License-Identifier: Apache-2.0
import json

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.domain.exceptions import ScriptGenerationError
from app.services.script.interface import GeneratedScript
from app.services.script.prompts import SLIDE_BLOCK, STYLE_REFERENCE_BLOCK, SYSTEM_PROMPT_V1

logger = structlog.get_logger(__name__)


class GeminiScriptGenerator:
    """Script generator using Gemini multimodal API (google-genai SDK)."""

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate(
        self,
        slide_image_png: bytes,
        slide_text: str,
        style_reference_transcript: str,
        extra_style_sample: str | None = None,
    ) -> GeneratedScript:
        from google import genai  # type: ignore[import-untyped,unused-ignore]
        from google.genai import types  # type: ignore[import-untyped,unused-ignore]

        client = genai.Client(api_key=settings.gemini_api_key)

        style_block = STYLE_REFERENCE_BLOCK.format(transcript=style_reference_transcript)
        if extra_style_sample:
            style_block += f"\n\nAdditional style sample:\n{extra_style_sample}"

        user_content = [
            style_block,
            SLIDE_BLOCK.format(slide_text=slide_text),
            types.Part.from_bytes(data=slide_image_png, mime_type="image/png"),
            "Generate the narration script as specified.",
        ]

        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT_V1,
                response_mime_type="application/json",
            ),
        )

        if response.text is None:
            raise ScriptGenerationError("Empty response from Gemini API")
        return self._parse_response(response.text)

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
