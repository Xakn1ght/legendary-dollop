#!/bin/bash

# ASSTROO Project Restore Script
# Restores a backup to set up the project on a new server

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔄 ASSTROO Project Restore${NC}"
echo "================================"
echo ""

# Check if backup file/directory is provided
if [ -z "$1" ]; then
    echo -e "${YELLOW}Usage: ./restore_project.sh <backup_file_or_directory>${NC}"
    echo ""
    echo "Examples:"
    echo "  ./restore_project.sh backups/astrobot_backup_20250101_120000.tar.gz"
    echo "  ./restore_project.sh backups/astrobot_backup_20250101_120000"
    echo ""
    exit 1
fi

BACKUP_SOURCE="$1"
PROJECT_DIR="/root/ASSTROO"
RESTORE_TEMP="/tmp/astrobot_restore_$$"

# Check if backup exists
if [ ! -f "$BACKUP_SOURCE" ] && [ ! -d "$BACKUP_SOURCE" ]; then
    echo -e "${RED}❌ Error: Backup not found: ${BACKUP_SOURCE}${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Extracting backup...${NC}"

# Extract if it's an archive
if [[ "$BACKUP_SOURCE" == *.tar.gz ]]; then
    mkdir -p "$RESTORE_TEMP"
    tar -xzf "$BACKUP_SOURCE" -C "$RESTORE_TEMP"
    BACKUP_DIR=$(find "$RESTORE_TEMP" -type d -name "astrobot_backup_*" | head -1)
elif [[ "$BACKUP_SOURCE" == *.zip ]]; then
    mkdir -p "$RESTORE_TEMP"
    unzip -q "$BACKUP_SOURCE" -d "$RESTORE_TEMP"
    BACKUP_DIR=$(find "$RESTORE_TEMP" -type d -name "astrobot_backup_*" | head -1)
else
    # It's already a directory
    BACKUP_DIR="$BACKUP_SOURCE"
fi

if [ -z "$BACKUP_DIR" ] || [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}❌ Error: Could not find backup directory${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Backup extracted${NC}"
echo ""

# Confirm restore
echo -e "${YELLOW}⚠️  This will restore the project from backup.${NC}"
echo "Backup location: $BACKUP_DIR"
echo "Project location: $PROJECT_DIR"
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled."
    rm -rf "$RESTORE_TEMP"
    exit 0
fi

echo ""
echo -e "${GREEN}[1/5]${NC} Restoring database..."
if [ -f "${BACKUP_DIR}/app/database/bot.db" ]; then
    mkdir -p "${PROJECT_DIR}/app/database"
    cp "${BACKUP_DIR}/app/database/bot.db" "${PROJECT_DIR}/app/database/bot.db"
    echo "   ✅ Database restored"
else
    echo "   ⚠️  Database file not found in backup"
fi

echo -e "${GREEN}[2/5]${NC} Restoring environment configuration..."
if [ -f "${BACKUP_DIR}/.env" ]; then
    cp "${BACKUP_DIR}/.env" "${PROJECT_DIR}/.env"
    echo "   ✅ .env file restored"
    echo -e "   ${YELLOW}⚠️  Please review .env file and update secrets if needed${NC}"
else
    echo "   ⚠️  .env file not found in backup"
    echo "   ${YELLOW}⚠️  You'll need to create .env file manually${NC}"
fi

echo -e "${GREEN}[3/5]${NC} Restoring configuration files..."
if [ -d "${BACKUP_DIR}/app/core" ]; then
    mkdir -p "${PROJECT_DIR}/app/core"
    cp -r "${BACKUP_DIR}/app/core"/*.json "${PROJECT_DIR}/app/core/" 2>/dev/null || true
    echo "   ✅ Configuration files restored"
fi

echo -e "${GREEN}[4/5]${NC} Restoring data files..."
if [ -d "${BACKUP_DIR}/app/data" ]; then
    mkdir -p "${PROJECT_DIR}/app/data"
    cp -r "${BACKUP_DIR}/app/data"/* "${PROJECT_DIR}/app/data/" 2>/dev/null || true
    echo "   ✅ Data files restored"
fi

echo -e "${GREEN}[5/6]${NC} Restoring database migrations..."
if [ -d "${BACKUP_DIR}/alembic" ]; then
    mkdir -p "${PROJECT_DIR}/alembic"
    cp -r "${BACKUP_DIR}/alembic"/* "${PROJECT_DIR}/alembic/" 2>/dev/null || true
    echo "   ✅ Migrations restored"
fi

echo -e "${GREEN}[6/6]${NC} Restoring application code..."
# Restore app directory
if [ -d "${BACKUP_DIR}/app" ]; then
    rsync -av \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        "${BACKUP_DIR}/app/" "${PROJECT_DIR}/app/" 2>/dev/null || true
    echo "   ✅ Application code restored"
fi

# Restore root files
if [ -f "${BACKUP_DIR}/requirements.txt" ]; then
    cp "${BACKUP_DIR}/requirements.txt" "${PROJECT_DIR}/" 2>/dev/null || true
fi
if [ -f "${BACKUP_DIR}/alembic.ini" ]; then
    cp "${BACKUP_DIR}/alembic.ini" "${PROJECT_DIR}/" 2>/dev/null || true
fi

# Cleanup temp directory
rm -rf "$RESTORE_TEMP"

echo ""
echo -e "${GREEN}✅ Restore Complete!${NC}"
echo "================================"
echo ""
echo "Next steps:"
echo "  1. Review and update .env file with your secrets"
echo "  2. Create virtual environment: python3 -m venv venv"
echo "  3. Activate venv: source venv/bin/activate"
echo "  4. Install dependencies: pip install -r requirements.txt"
echo "  5. Test the application: python -m app.main"
echo ""
echo -e "${YELLOW}⚠️  Important:${NC}"
echo "  - Check .env file for BOT_TOKEN and other secrets"
echo "  - Update database path if needed"
echo "  - Verify all configuration files"
echo ""
