# SPDX-License-Identifier: Apache-2.0
FROM node:24-slim AS builder
WORKDIR /app
# Copy pre-installed node_modules from host (avoids npm/registry calls at build time)
COPY node_modules ./node_modules
COPY . .
RUN node node_modules/next/dist/bin/next build

FROM node:24-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN groupadd --system --gid 1001 nodejs && useradd --system --uid 1001 --gid nodejs nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]
