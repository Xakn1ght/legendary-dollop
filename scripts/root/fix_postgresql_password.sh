#!/bin/bash

# Fix PostgreSQL Password Script

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 Fixing PostgreSQL Password${NC}"
echo "================================"
echo ""

# Database info
DB_NAME="yomastrbot_db"
DB_USER="astronaut_admin"
NEW_PASSWORD="6Y33zY!W@sHer39"

echo "Updating password for user: ${DB_USER}"
echo "Database: ${DB_NAME}"
echo ""

# Update password
sudo -u postgres psql << EOF
ALTER USER ${DB_USER} WITH PASSWORD '${NEW_PASSWORD}';
\q
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Password updated successfully${NC}"
else
    echo -e "${RED}❌ Failed to update password${NC}"
    exit 1
fi

# Update connection file
cat > /root/ASSTROO/postgresql_connection.txt << EOF
# PostgreSQL Connection Information
# Updated: $(date)

DATABASE_NAME=${DB_NAME}
DATABASE_USER=${DB_USER}
DATABASE_PASSWORD=${NEW_PASSWORD}
DATABASE_HOST=localhost
DATABASE_PORT=5432

# Connection String:
# postgresql+asyncpg://${DB_USER}:${NEW_PASSWORD}@localhost:5432/${DB_NAME}
EOF

echo -e "${GREEN}✅ Connection file updated${NC}"
echo ""

# Test connection
echo "Testing connection..."
sudo -u postgres psql -d ${DB_NAME} -U ${DB_USER} -c "SELECT 1;" <<< "${NEW_PASSWORD}" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Connection test successful${NC}"
else
    echo -e "${YELLOW}⚠️  Direct test failed, but password was updated${NC}"
    echo "   Try the migration script again"
fi

echo ""
echo -e "${GREEN}✅ Password fix complete!${NC}"
echo ""
echo "Connection string:"
echo "postgresql+asyncpg://${DB_USER}:${NEW_PASSWORD}@localhost:5432/${DB_NAME}"
echo ""
echo "Now run: python migrate_to_postgresql_v2.py"
