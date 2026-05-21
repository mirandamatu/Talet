#!/bin/sh
set -e

: "${BACKEND_PROXY_BASE:=http://backend:8000}"
: "${BACKEND_PROXY_HOST:=backend:8000}"
export BACKEND_PROXY_BASE BACKEND_PROXY_HOST

envsubst '${BACKEND_PROXY_BASE} ${BACKEND_PROXY_HOST}' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'
