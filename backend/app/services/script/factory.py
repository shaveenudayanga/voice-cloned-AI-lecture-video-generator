# SPDX-License-Identifier: Apache-2.0
from typing import cast

from app.core.config import settings
from app.services.script.interface import LLMScriptGenerator


def get_script_generator() -> LLMScriptGenerator:
    # Cast to str so the unreachable-branch guard below passes mypy's exhaustiveness check.
    provider = cast(str, settings.llm_provider)

    if provider == "ollama":
        from app.services.script.ollama_adapter import OllamaScriptGenerator

        return OllamaScriptGenerator()

    if provider == "gemini":
        from app.services.script.gemini_adapter import GeminiScriptGenerator

        return GeminiScriptGenerator()

    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Must be 'gemini' or 'ollama'.")
