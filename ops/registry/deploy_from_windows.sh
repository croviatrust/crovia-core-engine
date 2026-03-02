#!/bin/bash
# Deploy Windows local files to correct webroot paths
# Source of truth: Windows local -> Hetzner webroot -> repo sorgente

WEBROOT=/var/www/registry
REPO=/opt/crovia/hf_datasets/global-ai-training-omissions/webroot/registry
UPLOAD=/tmp/webroot_upload

# The scp uploaded flat files — we need to re-upload with correct structure
# This script assumes files are already in correct webroot paths
# Just sync webroot -> repo and update canonicals

echo "=== Verifica dimensioni post-upload ==="
stat -c '%s %n' \
    $WEBROOT/tpa/index.html \
    $WEBROOT/verify/index.html \
    $WEBROOT/provenance/index.html \
    $WEBROOT/index.html \
    $WEBROOT/omissions/index.html \
    $WEBROOT/ranking/index.html \
    $WEBROOT/compliance/index.html \
    $WEBROOT/outreach.html \
    $WEBROOT/cep/index.html 2>/dev/null

echo ""
echo "=== Sync webroot -> repo (mantieni speculare) ==="
rsync -av --exclude='data/' $WEBROOT/ $REPO/ 2>/dev/null | grep -v '/$\|sending\|sent\|total'

echo ""
echo "=== Aggiorna .canonical ==="
for f in tpa/index.html verify/index.html provenance/index.html index.html; do
    if [ -f "$WEBROOT/$f" ]; then
        cp "$WEBROOT/$f" "$WEBROOT/$f.canonical"
        echo "  Updated: $f.canonical ($(stat -c '%s' $WEBROOT/$f)b)"
    fi
done

echo ""
echo "=== Verifica TPA fix ==="
grep -n '_totalAvailable\|total_tpas' $WEBROOT/tpa/index.html | head -3
