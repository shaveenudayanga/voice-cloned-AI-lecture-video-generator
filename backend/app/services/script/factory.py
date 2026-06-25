# SPDX-License-Identifier: Apache-2.0
from app.core.config import settings
from app.services.script.interface import LLMScriptGenerator


def get_script_generator() -> LLMScriptGenerator:
    if settings.llm_provider == "ollama":
        from app.services.script.ollama_adapter import OllamaScriptGenerator

        return OllamaScriptGenerator()

    from app.services.script.gemini_adapter import GeminiScriptGenerator

    return GeminiScriptGenerator()
