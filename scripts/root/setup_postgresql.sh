#!/bin/bash

# PostgreSQL Setup Script for ASSTROO
# Installs PostgreSQL and creates database/user

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🗄️  PostgreSQL Setup for ASSTROO${NC}"
echo "================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}⚠️  This script needs sudo privileges${NC}"
    echo "Please run: sudo ./setup_postgresql.sh"
    exit 1
fi

# Step 1: Install PostgreSQL
echo -e "${BLUE}[1/4]${NC} Installing PostgreSQL..."
if command -v psql &> /dev/null; then
    PSQL_VERSION=$(psql --version | awk '{print $3}')
    echo -e "   ${GREEN}✅ PostgreSQL already installed (${PSQL_VERSION})${NC}"
else
    echo "   Installing PostgreSQL..."
    apt update
    apt install -y postgresql postgresql-contrib libpq-dev python3-dev
    echo -e "   ${GREEN}✅ PostgreSQL installed${NC}"
fi

# Step 2: Start PostgreSQL service
echo -e "${BLUE}[2/4]${NC} Starting PostgreSQL service..."
systemctl start postgresql
systemctl enable postgresql
echo -e "   ${GREEN}✅ PostgreSQL service started${NC}"

# Step 3: Create database and user
echo -e "${BLUE}[3/4]${NC} Creating database and user..."

# Get database name
read -p "Database name [astrobot]: " DB_NAME
DB_NAME=${DB_NAME:-astrobot}

# Get username
read -p "Database user [astrobot_user]: " DB_USER
DB_USER=${DB_USER:-astrobot_user}

# Get password
read -sp "Database password: " DB_PASSWORD
echo ""

if [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}❌ Password cannot be empty${NC}"
    exit 1
fi

# Create database and user
sudo -u postgres psql << EOF
-- Create database
CREATE DATABASE ${DB_NAME};

-- Create user
CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};

-- Allow user to create databases (for migrations)
ALTER USER ${DB_USER} CREATEDB;

-- Connect to database and grant schema privileges
\c ${DB_NAME}
GRANT ALL ON SCHEMA public TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DB_USER};

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${DB_USER};
EOF

if [ $? -eq 0 ]; then
    echo -e "   ${GREEN}✅ Database and user created${NC}"
else
    echo -e "   ${RED}❌ Failed to create database/user${NC}"
    exit 1
fi

# Step 4: Install Python dependencies
echo -e "${BLUE}[4/4]${NC} Installing Python dependencies..."

# Check if venv exists
if [ -d "/root/ASSTROO/venv" ]; then
    source /root/ASSTROO/venv/bin/activate
    pip install asyncpg
    echo -e "   ${GREEN}✅ asyncpg installed${NC}"
else
    echo -e "   ${YELLOW}⚠️  Virtual environment not found${NC}"
    echo "   Please create venv first: python3 -m venv venv"
fi

# Save connection info
cat > /root/ASSTROO/postgresql_connection.txt << EOF
# PostgreSQL Connection Information
# Generated: $(date)

DATABASE_NAME=${DB_NAME}
DATABASE_USER=${DB_USER}
DATABASE_PASSWORD=${DB_PASSWORD}
DATABASE_HOST=localhost
DATABASE_PORT=5432

# Connection String:
# postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
EOF

echo ""
echo -e "${GREEN}✅ PostgreSQL Setup Complete!${NC}"
echo "================================"
echo ""
echo "Database Information:"
echo "  Database: ${DB_NAME}"
echo "  User: ${DB_USER}"
echo "  Host: localhost"
echo "  Port: 5432"
echo ""
echo "Connection string saved to: postgresql_connection.txt"
echo ""
echo "Next step: Run migration script"
echo "  python migrate_to_postgresql.py"
echo ""
