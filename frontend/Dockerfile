FROM node:24.20.0-alpine3.23@sha256:0388af2af070cd4736a1567cfed02469ba117848845b4165d87a333edb53d2ca AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24.20.0-alpine3.23@sha256:0388af2af070cd4736a1567cfed02469ba117848845b4165d87a333edb53d2ca AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:24.20.0-alpine3.23@sha256:0388af2af070cd4736a1567cfed02469ba117848845b4165d87a333edb53d2ca AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN apk upgrade --no-cache \
    && addgroup -S nextjs \
    && adduser -S nextjs -G nextjs \
    && rm -rf \
        /opt/yarn-v1.22.22 \
        /usr/local/lib/node_modules/corepack \
        /usr/local/lib/node_modules/npm \
    && rm -f \
        /usr/local/bin/corepack \
        /usr/local/bin/npm \
        /usr/local/bin/npx \
        /usr/local/bin/yarn \
        /usr/local/bin/yarnpkg

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

ARG RELEASE_SHA=unknown
ENV RELEASE_SHA=$RELEASE_SHA
LABEL org.opencontainers.image.revision=$RELEASE_SHA

USER 100:101
EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]
