# SPDX-License-Identifier: Apache-2.0
"""
Prompt loader for versioned script-generation templates.

Templates live in docs/prompts/ (loaded by filename) — never hardcoded in Python.
Each template file has sections delimited by '## SECTION_NAME' markers.
"""
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parents[4] / "docs" / "prompts"

_STRICT_ADDENDUM = (
    "Reply with plain narration text only. No brackets, bullets, or markdown."
)


def _load_template(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _parse_sections(raw: str) -> dict[str, str]:
    """Split a template file into named sections on '## SECTION_NAME' markers."""
    sections: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    for line in raw.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(lines).strip()
            current = line[3:].strip()
            lines = []
        else:
            lines.append(line)
    if current is not None:
        sections[current] = "\n".join(lines).strip()
    return sections


def _sections_v1() -> dict[str, str]:
    raw = _load_template("script_generation_v1.md")
    return _parse_sections(raw)


def build_prompt_v1(
    slide_text: str,
    style_reference: str | None,
    pronunciation_hints: str | None,
) -> str:
    """Assemble the full prompt for a single slide from versioned template sections.

    The style-injection framing text ('Write in the speaking style of…') comes from
    the STYLE_REFERENCE_TEMPLATE section in the prompt file — never hardcoded here.
    """
    secs = _sections_v1()

    style_block = ""
    if style_reference:
        style_block = secs["STYLE_REFERENCE_TEMPLATE"].format(transcript=style_reference)

    pronunciation_block = ""
    if pronunciation_hints:
        pronunciation_block = secs["PRONUNCIATION_TEMPLATE"].format(hints=pronunciation_hints)

    slide_block = secs["SLIDE_TEMPLATE"].format(slide_text=slide_text)

    parts = [
        secs["SYSTEM_INSTRUCTION"],
        style_block,
        pronunciation_block,
        slide_block,
        secs["OUTPUT_FORMAT"],
    ]
    return "\n\n".join(p for p in parts if p)
