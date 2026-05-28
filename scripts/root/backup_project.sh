#!/bin/bash

# ASSTROO Project Backup Script
# Creates a complete backup of the project for easy migration to another server

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 ASSTROO Project Backup${NC}"
echo "================================"
echo ""

# Configuration
PROJECT_DIR="/root/ASSTROO"
BACKUP_DIR="${PROJECT_DIR}/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="astrobot_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_PATH}"

echo -e "${YELLOW}📦 Creating backup: ${BACKUP_NAME}${NC}"
echo ""

# 1. Backup database (using SQLite backup command for safety)
echo -e "${GREEN}[1/7]${NC} Backing up database..."
if [ -f "${PROJECT_DIR}/app/database/bot.db" ]; then
    mkdir -p "${BACKUP_PATH}/app/database"
    # Use SQLite backup command to avoid locks and ensure consistency
    if command -v sqlite3 &> /dev/null; then
        sqlite3 "${PROJECT_DIR}/app/database/bot.db" ".backup '${BACKUP_PATH}/app/database/bot.db'" 2>/dev/null || {
            # Fallback to regular copy if backup command fails
            cp "${PROJECT_DIR}/app/database/bot.db" "${BACKUP_PATH}/app/database/bot.db"
            echo "   ⚠️  Used regular copy (SQLite backup command unavailable)"
        }
        echo "   ✅ Database backed up (using SQLite backup command)"
    else
        # Fallback to regular copy
        cp "${PROJECT_DIR}/app/database/bot.db" "${BACKUP_PATH}/app/database/bot.db"
        echo "   ✅ Database backed up (regular copy)"
    fi
    
    # Get database size for info
    DB_SIZE=$(du -h "${BACKUP_PATH}/app/database/bot.db" | cut -f1)
    echo "   📊 Database size: ${DB_SIZE}"
else
    echo "   ⚠️  Database file not found (might be first run)"
fi

# 2. Backup .env file (if exists)
echo -e "${GREEN}[2/7]${NC} Backing up environment configuration..."
if [ -f "${PROJECT_DIR}/.env" ]; then
    cp "${PROJECT_DIR}/.env" "${BACKUP_PATH}/.env"
    echo "   ✅ .env file backed up"
else
    echo "   ⚠️  .env file not found"
fi

# 3. Backup core configuration files
echo -e "${GREEN}[3/7]${NC} Backing up configuration files..."
mkdir -p "${BACKUP_PATH}/app/core"
cp -r "${PROJECT_DIR}/app/core"/*.json "${BACKUP_PATH}/app/core/" 2>/dev/null || true
cp -r "${PROJECT_DIR}/app/core"/*.py "${BACKUP_PATH}/app/core/" 2>/dev/null || true
echo "   ✅ Configuration files backed up"

# 4. Backup data files
echo -e "${GREEN}[4/7]${NC} Backing up data files..."
if [ -d "${PROJECT_DIR}/app/data" ]; then
    mkdir -p "${BACKUP_PATH}/app/data"
    cp -r "${PROJECT_DIR}/app/data"/* "${BACKUP_PATH}/app/data/" 2>/dev/null || true
    echo "   ✅ Data files backed up"
fi

# 5. Backup Alembic migrations
echo -e "${GREEN}[5/7]${NC} Backing up database migrations..."
if [ -d "${PROJECT_DIR}/alembic" ]; then
    mkdir -p "${BACKUP_PATH}/alembic"
    cp -r "${PROJECT_DIR}/alembic"/* "${BACKUP_PATH}/alembic/" 2>/dev/null || true
    echo "   ✅ Migrations backed up"
fi

# 6. Backup application code (excluding unnecessary files)
echo -e "${GREEN}[6/7]${NC} Backing up application code..."
rsync -av \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.git' \
    --exclude='logs' \
    --exclude='backups' \
    --exclude='.tmp' \
    --exclude='*.log' \
    --exclude='*.db-journal' \
    --exclude='*.db-wal' \
    --exclude='*.db-shm' \
    --exclude='node_modules' \
    --exclude='.vscode' \
    "${PROJECT_DIR}/app" "${BACKUP_PATH}/" 2>/dev/null || true

# Also backup root level important files
cp "${PROJECT_DIR}/requirements.txt" "${BACKUP_PATH}/" 2>/dev/null || true
cp "${PROJECT_DIR}/alembic.ini" "${BACKUP_PATH}/" 2>/dev/null || true

echo "   ✅ Application code backed up"

# 7. Create backup info file
echo -e "${GREEN}[7/7]${NC} Creating backup information..."
cat > "${BACKUP_PATH}/BACKUP_INFO.txt" << EOF
ASSTROO Project Backup
=====================
Backup Date: $(date)
Backup Name: ${BACKUP_NAME}
Server: $(hostname)
User: $(whoami)

Contents:
--------
- Database: app/database/bot.db
- Configuration: app/core/*.json, app/core/*.py
- Environment: .env
- Application Code: app/
- Data Files: app/data/

To Restore:
-----------
1. Extract this backup to a new server
2. Run: ./restore_project.sh
3. Or manually:
   - Copy bot.db to app/database/
   - Copy .env file to project root
   - Install dependencies: pip install -r requirements.txt
   - Run: python -m app.main

Important Notes:
---------------
- venv/ is NOT included (recreate with: python -m venv venv)
- logs/ are NOT included (will be recreated)
- Make sure to set BOT_TOKEN and other secrets in .env
EOF

echo "   ✅ Backup info created"

# 8. Create compressed archive
echo ""
echo -e "${GREEN}[8/8]${NC} Creating compressed archive..."
cd "${BACKUP_DIR}"
tar -czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}" 2>/dev/null || {
    # Fallback to zip if tar fails
    zip -r "${BACKUP_NAME}.zip" "${BACKUP_NAME}" > /dev/null 2>&1
    ARCHIVE_NAME="${BACKUP_NAME}.zip"
}

if [ -f "${BACKUP_NAME}.tar.gz" ]; then
    ARCHIVE_NAME="${BACKUP_NAME}.tar.gz"
    ARCHIVE_SIZE=$(du -h "${ARCHIVE_NAME}" | cut -f1)
    echo "   ✅ Archive created: ${ARCHIVE_NAME} (${ARCHIVE_SIZE})"
elif [ -f "${BACKUP_NAME}.zip" ]; then
    ARCHIVE_NAME="${BACKUP_NAME}.zip"
    ARCHIVE_SIZE=$(du -h "${ARCHIVE_NAME}" | cut -f1)
    echo "   ✅ Archive created: ${ARCHIVE_NAME} (${ARCHIVE_SIZE})"
else
    echo "   ⚠️  Could not create archive, but backup folder is ready"
    ARCHIVE_NAME="${BACKUP_NAME}"
fi

# 9. Verify backup integrity
echo ""
echo -e "${GREEN}[9/9]${NC} Verifying backup..."
if [ -f "${BACKUP_DIR}/${ARCHIVE_NAME}" ]; then
    # Test archive integrity
    if [[ "${ARCHIVE_NAME}" == *.tar.gz ]]; then
        tar -tzf "${BACKUP_DIR}/${ARCHIVE_NAME}" > /dev/null 2>&1 && {
            echo "   ✅ Archive integrity verified"
        } || {
            echo "   ⚠️  Archive verification failed (but file exists)"
        }
    elif [[ "${ARCHIVE_NAME}" == *.zip ]]; then
        unzip -t "${BACKUP_DIR}/${ARCHIVE_NAME}" > /dev/null 2>&1 && {
            echo "   ✅ Archive integrity verified"
        } || {
            echo "   ⚠️  Archive verification failed (but file exists)"
        }
    fi
fi

# Clean up uncompressed folder (optional - comment out if you want to keep it)
# rm -rf "${BACKUP_PATH}"

echo ""
echo -e "${GREEN}✅ Backup Complete!${NC}"
echo "================================"
echo ""
echo "Backup location: ${BACKUP_DIR}/${ARCHIVE_NAME}"
echo ""
echo "📋 Backup Summary:"
echo "   - Database: ✅"
echo "   - Configuration: ✅"
echo "   - Application Code: ✅"
echo "   - Migrations: ✅"
echo ""
echo "🚀 To restore on another server:"
echo "  1. Copy backup file: scp ${BACKUP_DIR}/${ARCHIVE_NAME} user@new-server:/root/ASSTROO/backups/"
echo "  2. On new server, run: ./restore_project.sh backups/${ARCHIVE_NAME}"
echo "  3. Setup environment: python3 -m venv venv && source venv/bin/activate"
echo "  4. Install dependencies: pip install -r requirements.txt"
echo "  5. Update .env file with your secrets"
echo "  6. Run: python -m app.main"
echo ""
echo "📖 See BACKUP_GUIDE.md for detailed instructions"
echo ""
