FROM nginx:1.30.6-alpine3.24@sha256:0e52bd054126cdc040b1276c0af347aeb02a41b9cfe305d6094767ac30e97949

# The upstream image can lag Alpine security package releases even when the
# Nginx patch itself is current. Require the fixed expat release as well as
# upgrading the remaining packages so a cached older package cannot persist.
RUN apk add --no-cache 'libexpat>=2.9.0-r0' \
    && apk upgrade --no-cache \
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
