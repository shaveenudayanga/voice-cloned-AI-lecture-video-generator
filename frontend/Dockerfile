# SPDX-License-Identifier: Apache-2.0
FROM node:24-slim AS builder
WORKDIR /app

# Enable pnpm via corepack (version pinned in package.json#packageManager)
RUN corepack enable

# Install dependencies before copying source so this layer is cached on re-builds
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

ARG NEXT_PUBLIC_API_KEY
ENV NEXT_PUBLIC_API_KEY=$NEXT_PUBLIC_API_KEY
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY . .
RUN pnpm build

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
# Bind to all interfaces (incl. loopback) so the in-container healthcheck can
# reach the server; the Next standalone server defaults to a single interface.
ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
