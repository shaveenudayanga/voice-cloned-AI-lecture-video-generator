#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Seed the database with sample data for local development."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


async def main() -> None:
    print("Seed script — Phase 2+ will populate sample projects, slides, and voice profiles.")
    print("Database URL read from DATABASE_URL env var.")


if __name__ == "__main__":
    asyncio.run(main())
