#!/bin/bash

# Quick test script - Creates backup and verifies it immediately

echo "🧪 Testing Backup System"
echo "========================"
echo ""

# Step 1: Create backup
echo "Step 1: Creating backup..."
cd /root/ASSTROO
./backup_project.sh

# Get the latest backup
LATEST_BACKUP=$(ls -t backups/astrobot_backup_*.tar.gz 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ No backup found. Check backup_project.sh output above."
    exit 1
fi

echo ""
echo "Step 2: Verifying backup..."
echo ""

# Step 2: Verify backup
./verify_backup.sh "$LATEST_BACKUP"

echo ""
echo "✅ Test complete!"
echo ""
echo "If you see 'BACKUP VERIFIED' above, your backup is working perfectly! 🎉"
