// SPDX-License-Identifier: Apache-2.0
// Tailwind CSS v4 is processed via its PostCSS plugin. Without this config Next.js
// never runs the plugin, so `@import "tailwindcss"` and `@theme` are emitted raw and
// no utility classes are generated (the app renders as unstyled HTML).
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};

export default config;
