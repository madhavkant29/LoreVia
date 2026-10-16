FROM redis:7.4.11-alpine3.21@sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499

# Security gate: the upstream image can lag Alpine security package releases
# even when the Redis patch itself is current. Build the release cache with
# available fixes; the container-image-scan CI job verifies the result.
RUN apk upgrade --no-cache

# Match the runtime contract: production Compose and the health check run Redis
# as the unprivileged redis user instead of root.
USER 999:1000
