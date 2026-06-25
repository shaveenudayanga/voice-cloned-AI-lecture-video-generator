# ADR-0012 — Project Source License: Apache-2.0

**Status:** Accepted  
**Date:** 2026-06-25

## Context

We need to choose the license for the project's own source code (distinct from the model dependency licenses documented in `LICENSE_AUDIT.md`). The professor wants the project to be free and open-source; future forks by other academics or labs are expected.

## Decision

License the project source under **Apache-2.0**.

Rationale over MIT:
- Apache-2.0 includes an **explicit patent grant** — important if the professor's lab or a downstream fork ever involves patented technology or commercializes a derivative.
- Apache-2.0 requires preservation of attribution notices, which is appropriate for an academic project.
- Both licenses are permissive and compatible with all our dependencies (MIT, BSD-3, PostgreSQL License, MPL 2.0, Apache-2.0).

All `.py` and `.ts` source files carry `SPDX-License-Identifier: Apache-2.0` headers. The `LICENSE` file at the repo root contains the full Apache-2.0 text.

The non-commercial model weights (F5-TTS CC-BY-NC-4.0, XTTS-v2 CPML) are runtime dependencies — they are not distributed in the source tree and do not affect the source license.

## Consequences

- All new source files must include `SPDX-License-Identifier: Apache-2.0`.
- The `scripts/license-audit.py` script verifies dependency licenses but not SPDX headers — a future CI check (`reuse lint`) could enforce this.
- Commercial forks must comply with Apache-2.0 attribution requirements AND must replace the CC-BY-NC-4.0 and CPML model dependencies.
