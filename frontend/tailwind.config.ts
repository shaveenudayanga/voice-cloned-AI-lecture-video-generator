// SPDX-License-Identifier: Apache-2.0
// Minimal config — theme lives in app/globals.css under @theme (Tailwind v4 CSS-first)
import type { Config } from "tailwindcss";

export default {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
} satisfies Config;
