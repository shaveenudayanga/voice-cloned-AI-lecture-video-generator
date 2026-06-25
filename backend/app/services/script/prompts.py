# SPDX-License-Identifier: Apache-2.0
"""
Versioned prompt templates for script generation.
Prompts are also stored as plain markdown in docs/prompts/ for auditability.
"""
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "docs" / "prompts"


SYSTEM_PROMPT_V1 = """\
You are a university lecture script writer. Your job is to write a clear, engaging spoken \
narration for a single lecture slide. The narration should:
- Explain the concepts on the slide, not just read the text verbatim
- Use the vocabulary, sentence structure, and register found in the style reference below
- Be suitable for text-to-speech synthesis (no bullet symbols, no markdown, no URLs)
- Be approximately 30-90 seconds when spoken at a natural pace
- End naturally, as if the professor will advance to the next slide

Respond with a JSON object with exactly these fields:
{
  "narration_text": "<the full spoken script>",
  "estimated_reading_time_s": <float seconds>,
  "pronunciation_hints": "<optional: comma-separated word=phonetic pairs, or null>"
}
"""

STYLE_REFERENCE_BLOCK = """\
## Professor's style reference
The following is a transcript of the professor's own speech. Mirror this vocabulary, \
phrasing, and sentence rhythm in the generated script:

{transcript}
"""

SLIDE_BLOCK = """\
## Slide content
{slide_text}
"""
