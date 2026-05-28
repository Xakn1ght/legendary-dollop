# 💾 ASSTROO Project Backup Guide

## Quick Start

### Create a Backup
```bash
cd /root/ASSTROO
./backup_project.sh
```

This creates a compressed backup in `backups/` folder.

### Restore on Another Server
```bash
# 1. Copy backup file to new server
scp backups/astrobot_backup_*.tar.gz user@new-server:/root/ASSTROO/backups/

# 2. On new server, extract and restore
cd /root/ASSTROO
./restore_project.sh backups/astrobot_backup_*.tar.gz
```

---

## What Gets Backed Up

✅ **Included:**
- Database file (`app/database/bot.db`)
- Environment config (`.env`)
- Configuration files (`app/core/*.json`, `app/core/*.py`)
- Application code (`app/`)
- Data files (`app/data/`)
- Requirements file (`requirements.txt`)

❌ **Excluded:**
- Virtual environment (`venv/`) - recreate on new server
- Logs (`logs/`) - will be recreated
- Cache files (`__pycache__/`, `*.pyc`)
- Git history (`.git/`)
- Temporary files (`.tmp/`)

---

## Backup Locations

- **Backup folder**: `/root/ASSTROO/backups/`
- **Format**: `astrobot_backup_YYYYMMDD_HHMMSS.tar.gz`
- **Size**: Usually 10-50 MB (depends on database size)

---

## Manual Backup (Alternative)

If you prefer manual backup:

```bash
# 1. Backup database
cp app/database/bot.db app/database/bot.db.backup

# 2. Backup .env
cp .env .env.backup

# 3. Create full archive
tar -czf astrobot_backup_$(date +%Y%m%d).tar.gz \
    app/ \
    .env \
    requirements.txt \
    alembic/ \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='logs' \
    --exclude='*.pyc'
```

---

## Restore Process

### Automatic Restore
```bash
./restore_project.sh backups/astrobot_backup_20250101_120000.tar.gz
```

### Manual Restore
```bash
# 1. Extract backup
tar -xzf astrobot_backup_*.tar.gz

# 2. Copy files
cp -r extracted_backup/app/* /root/ASSTROO/app/
cp extracted_backup/.env /root/ASSTROO/.env
cp extracted_backup/app/database/bot.db /root/ASSTROO/app/database/bot.db

# 3. Setup environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Setting Up on New Server

After restoring backup:

1. **Install Python dependencies:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Update .env file:**
   ```bash
   nano .env
   # Update:
   # - BOT_TOKEN
   # - ADMIN_ID
   # - MARZBAN credentials
   # - Database URL (if changed)
   ```

3. **Test the application:**
   ```bash
   python -m app.main
   ```

4. **Run as service (optional):**
   ```bash
   # Create systemd service
   sudo nano /etc/systemd/system/astrobot.service
   ```

---

## Automated Backups (Cron Job)

Set up daily automatic backups:

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 2 AM)
0 2 * * * /root/ASSTROO/backup_project.sh >> /root/ASSTROO/backups/backup.log 2>&1

# Keep only last 7 backups (add to backup script)
# Or manually clean old backups:
find /root/ASSTROO/backups -name "*.tar.gz" -mtime +7 -delete
```

---

## Backup Verification

Check if backup is valid:

```bash
# List contents
tar -tzf backups/astrobot_backup_*.tar.gz | head -20

# Test extraction (dry run)
tar -xzf backups/astrobot_backup_*.tar.gz -C /tmp/test_restore
ls -la /tmp/test_restore/
rm -rf /tmp/test_restore
```

---

## Troubleshooting

### Backup fails
- Check disk space: `df -h`
- Check permissions: `ls -la backup_project.sh`
- Run manually to see errors

### Restore fails
- Check backup file integrity: `file backups/*.tar.gz`
- Verify paths exist: `ls -la /root/ASSTROO/`
- Check .env file format

### Database locked
- Stop the bot before backup
- Or use SQLite backup command:
  ```bash
  sqlite3 app/database/bot.db ".backup app/database/bot.db.backup"
  ```

---

## Best Practices

1. **Regular Backups**: Daily or weekly
2. **Test Restores**: Periodically test restore on test server
3. **Offsite Backup**: Copy backups to another server/cloud
4. **Version Control**: Keep multiple backup versions
5. **Documentation**: Note any manual changes needed

---

## Cloud Backup (Optional)

### Upload to Cloud Storage

**Using S3 (AWS):**
```bash
aws s3 cp backups/astrobot_backup_*.tar.gz s3://your-bucket/backups/
```

**Using rsync to another server:**
```bash
rsync -avz backups/ user@backup-server:/backups/astrobot/
```

**Using scp:**
```bash
scp backups/astrobot_backup_*.tar.gz user@backup-server:/backups/
```

---

## Security Notes

⚠️ **Important:**
- `.env` file contains secrets - keep backups secure
- Don't commit backups to Git
- Encrypt backups if storing offsite
- Use secure transfer (scp, rsync over SSH)

---

## Quick Reference

| Task | Command |
|------|---------|
| Create backup | `./backup_project.sh` |
| Restore backup | `./restore_project.sh <backup_file>` |
| List backups | `ls -lh backups/` |
| Delete old backups | `find backups -name "*.tar.gz" -mtime +7 -delete` |
| Check backup size | `du -h backups/*.tar.gz` |

---

**Ready to migrate?** After creating backup, you can safely proceed with PostgreSQL migration! 🚀
