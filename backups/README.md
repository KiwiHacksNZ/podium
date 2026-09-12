# Database Backups

## Create Backup

```bash
./scripts/backup-db.sh
```

Creates:
- `*.dump` — Full backup (use to restore)
- `*_csv/` — Each table as CSV (use to inspect data)

## Restore

```bash
./scripts/restore-db.sh            # latest .dump
./scripts/restore-db.sh backups/podium_20260421_120000.dump  # specific file
```
