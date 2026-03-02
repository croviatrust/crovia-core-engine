#!/bin/bash
echo "=== Dimensioni su disco ==="
stat -c '%s %n' \
    /var/www/registry/tpa/index.html \
    /var/www/registry/verify/index.html \
    /var/www/registry/provenance/index.html \
    /var/www/registry/index.html \
    /var/www/registry/omissions/index.html \
    /var/www/registry/ranking/index.html \
    /var/www/registry/compliance/index.html 2>/dev/null

echo ""
echo "=== Content-Length servito da nginx (bypass CF) ==="
for path in /registry/tpa /registry/verify /registry/provenance/ /registry/omissions /registry/ranking /registry/compliance; do
    SIZE=$(curl -sk --resolve "registry.croviatrust.com:443:127.0.0.1" \
        "https://registry.croviatrust.com${path}" 2>/dev/null | wc -c)
    echo "  ${path}: ${SIZE} bytes served"
done

echo ""
echo "=== Content-Length via CF (pubblico) ==="
for path in /registry/tpa /registry/verify /registry/provenance/; do
    SIZE=$(curl -sI "https://registry.croviatrust.com${path}" 2>/dev/null | grep -i content-length | awk '{print $2}' | tr -d '\r')
    CF=$(curl -sI "https://registry.croviatrust.com${path}" 2>/dev/null | grep -i cf-cache | tr -d '\r\n')
    echo "  ${path}: Content-Length=${SIZE} | ${CF}"
done
