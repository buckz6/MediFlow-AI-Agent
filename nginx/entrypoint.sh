#!/bin/sh
# Substitusi placeholder domain di nginx.conf sebelum Nginx start
set -e

if [ -z "$DOMAIN" ]; then
  echo "ERROR: DOMAIN environment variable is not set" >&2
  exit 1
fi

sed -i "s/MEDIFLOW_DOMAIN/${DOMAIN}/g" /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
