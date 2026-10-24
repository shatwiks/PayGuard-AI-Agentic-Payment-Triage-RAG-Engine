# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# PayGuard AI — Next.js 16 Production & Staging Frontend Containerfile
# Multi-stage standalone build with non-root security isolation
# ---------------------------------------------------------------------------

# Stage 1: Install Dependencies
FROM node:22-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# Stage 2: Production Build
FROM node:22-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG NEXT_PUBLIC_API_URL="http://localhost:8000/api/v1"
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# Stage 3: Minimal Standalone Runner
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Create non-root user
RUN addgroup --system --gid 10001 nodejs && \
    adduser --system --uid 10001 nextjs

# Copy public assets and standalone output
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "fetch('http://localhost:3000/login').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "server.js"]
