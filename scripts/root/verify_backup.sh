#!/bin/bash

# ASSTROO Backup Verification Script
# Tests if a backup is valid and contains real data

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔍 ASSTROO Backup Verification${NC}"
echo "================================"
echo ""

# Check if backup file is provided
if [ -z "$1" ]; then
    echo -e "${YELLOW}Usage: ./verify_backup.sh <backup_file>${NC}"
    echo ""
    echo "Examples:"
    echo "  ./verify_backup.sh backups/astrobot_backup_20250101_120000.tar.gz"
    echo "  ./verify_backup.sh backups/astrobot_backup_20250101_120000"
    echo ""
    exit 1
fi

BACKUP_SOURCE="$1"
TEMP_DIR="/tmp/backup_verify_$$"
VERIFIED=true

# Cleanup function
cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

echo -e "${YELLOW}📦 Analyzing backup: ${BACKUP_SOURCE}${NC}"
echo ""

# Check if backup exists
if [ ! -f "$BACKUP_SOURCE" ] && [ ! -d "$BACKUP_SOURCE" ]; then
    echo -e "${RED}❌ Error: Backup not found: ${BACKUP_SOURCE}${NC}"
    exit 1
fi

# Extract if it's an archive
if [[ "$BACKUP_SOURCE" == *.tar.gz ]]; then
    echo -e "${BLUE}[1/7]${NC} Extracting archive..."
    mkdir -p "$TEMP_DIR"
    if tar -xzf "$BACKUP_SOURCE" -C "$TEMP_DIR" 2>/dev/null; then
        echo -e "   ${GREEN}✅ Archive extracted successfully${NC}"
        BACKUP_DIR=$(find "$TEMP_DIR" -type d -name "astrobot_backup_*" | head -1)
    else
        echo -e "   ${RED}❌ Failed to extract archive (corrupted?)${NC}"
        exit 1
    fi
elif [[ "$BACKUP_SOURCE" == *.zip ]]; then
    echo -e "${BLUE}[1/7]${NC} Extracting archive..."
    mkdir -p "$TEMP_DIR"
    if unzip -q "$BACKUP_SOURCE" -d "$TEMP_DIR" 2>/dev/null; then
        echo -e "   ${GREEN}✅ Archive extracted successfully${NC}"
        BACKUP_DIR=$(find "$TEMP_DIR" -type d -name "astrobot_backup_*" | head -1)
    else
        echo -e "   ${RED}❌ Failed to extract archive (corrupted?)${NC}"
        exit 1
    fi
else
    # It's already a directory
    BACKUP_DIR="$BACKUP_SOURCE"
fi

if [ -z "$BACKUP_DIR" ] || [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}❌ Error: Could not find backup directory${NC}"
    exit 1
fi

echo ""

# Check database file
echo -e "${BLUE}[2/7]${NC} Verifying database..."
DB_FILE="${BACKUP_DIR}/app/database/bot.db"
if [ -f "$DB_FILE" ]; then
    DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
    echo -e "   ${GREEN}✅ Database file found (${DB_SIZE})${NC}"
    
    # Check if database is valid SQLite
    if command -v sqlite3 &> /dev/null; then
        # Check database integrity
        INTEGRITY=$(sqlite3 "$DB_FILE" "PRAGMA integrity_check;" 2>/dev/null)
        if [ "$INTEGRITY" = "ok" ]; then
            echo -e "   ${GREEN}✅ Database integrity check passed${NC}"
        else
            echo -e "   ${RED}❌ Database integrity check failed: ${INTEGRITY}${NC}"
            VERIFIED=false
        fi
        
        # Check if database has tables
        TABLE_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "0")
        if [ "$TABLE_COUNT" -gt "0" ]; then
            echo -e "   ${GREEN}✅ Database contains ${TABLE_COUNT} tables${NC}"
            
            # Check if users table exists and has data
            if sqlite3 "$DB_FILE" "SELECT name FROM sqlite_master WHERE type='table' AND name='users';" 2>/dev/null | grep -q "users"; then
                USER_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "0")
                echo -e "   ${GREEN}✅ Users table found with ${USER_COUNT} users${NC}"
            fi
        else
            echo -e "   ${YELLOW}⚠️  Database has no tables (might be empty)${NC}"
        fi
    else
        echo -e "   ${YELLOW}⚠️  sqlite3 not available (skipping integrity check)${NC}"
    fi
else
    echo -e "   ${RED}❌ Database file not found${NC}"
    VERIFIED=false
fi

echo ""

# Check .env file
echo -e "${BLUE}[3/7]${NC} Verifying environment configuration..."
if [ -f "${BACKUP_DIR}/.env" ]; then
    ENV_SIZE=$(wc -l < "${BACKUP_DIR}/.env")
    echo -e "   ${GREEN}✅ .env file found (${ENV_SIZE} lines)${NC}"
    
    # Check for important keys (without showing values)
    if grep -q "BOT_TOKEN=" "${BACKUP_DIR}/.env"; then
        echo -e "   ${GREEN}✅ BOT_TOKEN found${NC}"
    else
        echo -e "   ${YELLOW}⚠️  BOT_TOKEN not found${NC}"
    fi
    
    if grep -q "ADMIN_ID=" "${BACKUP_DIR}/.env"; then
        echo -e "   ${GREEN}✅ ADMIN_ID found${NC}"
    else
        echo -e "   ${YELLOW}⚠️  ADMIN_ID not found${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  .env file not found (you'll need to create it)${NC}"
fi

echo ""

# Check application code
echo -e "${BLUE}[4/7]${NC} Verifying application code..."
if [ -d "${BACKUP_DIR}/app" ]; then
    APP_FILES=$(find "${BACKUP_DIR}/app" -type f -name "*.py" | wc -l)
    echo -e "   ${GREEN}✅ Application directory found (${APP_FILES} Python files)${NC}"
    
    # Check for key files
    KEY_FILES=("src/app/main.py" "src/app/database/models.py" "src/app/core/settings/__init__.py")
    for file in "${KEY_FILES[@]}"; do
        if [ -f "${BACKUP_DIR}/${file}" ]; then
            echo -e "   ${GREEN}✅ ${file} found${NC}"
        else
            echo -e "   ${RED}❌ ${file} missing${NC}"
            VERIFIED=false
        fi
    done
else
    echo -e "   ${RED}❌ Application directory not found${NC}"
    VERIFIED=false
fi

echo ""

# Check configuration files
echo -e "${BLUE}[5/7]${NC} Verifying configuration files..."
if [ -d "${BACKUP_DIR}/app/core" ]; then
    CONFIG_FILES=$(find "${BACKUP_DIR}/app/core" -type f \( -name "*.json" -o -name "*.py" \) | wc -l)
    echo -e "   ${GREEN}✅ Configuration directory found (${CONFIG_FILES} files)${NC}"
else
    echo -e "   ${YELLOW}⚠️  Configuration directory not found${NC}"
fi

echo ""

# Check data files
echo -e "${BLUE}[6/7]${NC} Verifying data files..."
if [ -d "${BACKUP_DIR}/app/data" ]; then
    DATA_FILES=$(find "${BACKUP_DIR}/app/data" -type f | wc -l)
    echo -e "   ${GREEN}✅ Data directory found (${DATA_FILES} files)${NC}"
else
    echo -e "   ${YELLOW}⚠️  Data directory not found (might be empty)${NC}"
fi

echo ""

# Check requirements.txt
echo -e "${BLUE}[7/7]${NC} Verifying dependencies file..."
if [ -f "${BACKUP_DIR}/requirements.txt" ]; then
    DEP_COUNT=$(wc -l < "${BACKUP_DIR}/requirements.txt")
    echo -e "   ${GREEN}✅ requirements.txt found (${DEP_COUNT} dependencies)${NC}"
else
    echo -e "   ${YELLOW}⚠️  requirements.txt not found${NC}"
fi

echo ""
echo "================================"

# Final verdict
if [ "$VERIFIED" = true ]; then
    echo -e "${GREEN}✅ BACKUP VERIFIED - Ready to use!${NC}"
    echo ""
    echo "This backup contains:"
    echo "  ✅ Valid database with data"
    echo "  ✅ Application code"
    echo "  ✅ Configuration files"
    echo "  ✅ All necessary components"
    echo ""
    echo -e "${GREEN}You can safely use this backup to restore on another server!${NC}"
    exit 0
else
    echo -e "${RED}❌ BACKUP VERIFICATION FAILED${NC}"
    echo ""
    echo "Some critical components are missing or corrupted."
    echo "Please create a new backup."
    exit 1
fi
