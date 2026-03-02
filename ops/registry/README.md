# Registry Ops Scripts (OPEN)

Operational scripts for public registry maintenance on Hetzner.

## Files

- `deploy_from_windows.sh`: post-upload integrity checks + webroot->repo sync + canonical refresh.
- `check_served_vs_disk.sh`: compare on-disk files vs served responses (origin and public).
- `fix_sync_definitive.py`: patch sync behavior and refresh canonical files safely.

## Scope

These scripts are OPEN operations only (no PRO-only business logic, no hardcoded secrets).

## Notes

- Verify route is standardized to `verify/index.html`.
- Keep HF push disabled in operational repos where HF is blocked.
- Run scripts on Hetzner with least privilege required.
