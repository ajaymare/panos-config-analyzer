#!/bin/bash

# Generate self-signed certificate if not present
if [ ! -f /etc/nginx/ssl/server.crt ]; then
    mkdir -p /etc/nginx/ssl
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/server.key \
        -out /etc/nginx/ssl/server.crt \
        -subj "/C=US/ST=CA/L=SantaClara/O=PaloAlto/CN=panos-parser"
fi

# Start gunicorn in background
gunicorn -w 2 --threads 4 -b 127.0.0.1:8080 app:app &

# Start nginx in foreground
nginx -g 'daemon off;'
