#!/bin/sh
set -eu

edge_proxy_secret="${EDGE_PROXY_SECRET:-}"
if [ -z "${edge_proxy_secret}" ]; then
    secret_file="${EDGE_PROXY_SECRET_FILE:-/run/secrets/edge_proxy_secret}"
    if [ ! -r "${secret_file}" ]; then
        echo "Nginx edge-proxy secret is unavailable." >&2
        exit 1
    fi
    edge_proxy_secret="$(cat "${secret_file}")"
fi
secret_length="${#edge_proxy_secret}"
if [ "${secret_length}" -lt 32 ] || [ "${secret_length}" -gt 128 ]; then
    echo "Nginx edge-proxy secret must contain 32-128 URL-safe characters." >&2
    exit 1
fi
if ! printf '%s' "${edge_proxy_secret}" | grep -Eq '^[A-Za-z0-9_-]+$'; then
    echo "Nginx edge-proxy secret must contain 32-128 URL-safe characters." >&2
    exit 1
fi

umask 077
mkdir -p /tmp/nginx-conf.d
cp /opt/lorevia/nginx/runtime-paths.conf /tmp/nginx-conf.d/00-runtime-paths.conf
EDGE_PROXY_SECRET="${edge_proxy_secret}" \
    envsubst '${EDGE_PROXY_SECRET}' \
    < /opt/lorevia/nginx/default.conf.template \
    > /tmp/nginx-conf.d/default.conf
unset edge_proxy_secret EDGE_PROXY_SECRET

exec nginx -g 'daemon off;'
