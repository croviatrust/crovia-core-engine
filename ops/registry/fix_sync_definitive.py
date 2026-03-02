import os

# ============================================================
# FIX 1: Remove git reset --hard from sync script
# ============================================================
sync_path = '/usr/local/bin/crovia-sync-registry'
with open(sync_path) as f:
    c = f.read()

OLD_BLOCK = """git pull --rebase --autostash origin main 2>&1 || {
    echo "[CROVIA SYNC] git pull failed, attempting hard reset..."
    git stash 2>/dev/null || true
    git fetch origin main
    git reset --hard origin/main
    git stash pop 2>/dev/null || true
}"""

NEW_BLOCK = """git pull --rebase --autostash origin main 2>&1 || {
    echo "[CROVIA SYNC] git pull failed (HF locked) — keeping local commits, skipping reset"
}"""

if OLD_BLOCK in c:
    c = c.replace(OLD_BLOCK, NEW_BLOCK)
    with open(sync_path, 'w') as f:
        f.write(c)
    print('[OK] Removed git reset --hard from sync script')
elif 'keeping local commits' in c:
    print('[SKIP] sync script already patched')
else:
    print('[WARN] git reset block not found — printing git lines:')
    for i, line in enumerate(c.splitlines(), 1):
        if 'reset' in line or 'pull' in line or 'stash' in line:
            print(f'  L{i}: {line}')

# ============================================================
# FIX 2: Update .canonical files with current correct versions
# ============================================================
canonical_pairs = [
    ('/var/www/registry/tpa/index.html',         '/var/www/registry/tpa/index.html.canonical'),
    ('/var/www/registry/index.html',             '/var/www/registry/index.html.canonical'),
    ('/var/www/registry/provenance/index.html',  '/var/www/registry/provenance/index.html.canonical'),
    ('/var/www/registry/verify/index.html',      '/var/www/registry/verify/index.html.canonical'),
]

print('\n[Updating .canonical files]')
import shutil
for current, canonical in canonical_pairs:
    if os.path.exists(current):
        cur_size = os.path.getsize(current)
        can_size = os.path.getsize(canonical) if os.path.exists(canonical) else 0
        shutil.copy2(current, canonical)
        print(f'  [OK] {canonical} updated ({can_size}b -> {cur_size}b)')
    else:
        print(f'  [SKIP] {current} not found')

# ============================================================
# FIX 3: Update repo source files to match webroot
# ============================================================
repo_pairs = [
    ('/var/www/registry/tpa/index.html',
     '/opt/crovia/hf_datasets/global-ai-training-omissions/webroot/registry/tpa/index.html'),
]

print('\n[Syncing repo source files]')
for webroot, repo in repo_pairs:
    if os.path.exists(webroot):
        shutil.copy2(webroot, repo)
        print(f'  [OK] {repo} updated')

print('\n[DONE] All fixes applied')
