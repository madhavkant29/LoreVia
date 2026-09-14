FROM nginx:1.30.4-alpine3.24@sha256:dc5069ad14f19660b141b21236140b91656bf89bbc3e2417c70ae650cd66104c

# The upstream image can lag Alpine security package releases even when the
# Nginx patch itself is current. Build the release proxy with available fixes.
RUN apk upgrade --no-cache \
    && sed -i 's#^user  nginx;##; s#pid        /run/nginx.pid;#pid        /tmp/nginx.pid;#; s#include /etc/nginx/conf.d/\*.conf;#include /tmp/nginx-conf.d/*.conf;#' /etc/nginx/nginx.conf \
    && mkdir -p /opt/lorevia/nginx

COPY ops/nginx/runtime-paths.conf /opt/lorevia/nginx/runtime-paths.conf
COPY ops/nginx/nginx.conf /opt/lorevia/nginx/default.conf.template
COPY ops/nginx/start.sh /usr/local/bin/lorevia-nginx-start
RUN chmod 0555 /usr/local/bin/lorevia-nginx-start \
    && chmod 0444 /opt/lorevia/nginx/runtime-paths.conf /opt/lorevia/nginx/default.conf.template

EXPOSE 8080 8443
USER 101:101
ENTRYPOINT ["/usr/local/bin/lorevia-nginx-start"]
