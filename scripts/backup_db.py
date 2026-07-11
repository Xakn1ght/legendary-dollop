#!/usr/bin/env python3
"""
Database backup script - Creates a full backup before reset.

Usage:
    python scripts/backup_db.py [--output-dir backups/]

This script will:
1. Backup PostgreSQL database (pg_dump)
2. Backup important JSON files (user_state.json, admin sessions, etc.)
3. Create timestamped backup folder
4. Optionally backup .env (without secrets)
"""

import asyncio
import sys
import os
import subprocess
import shutil
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, unquote

# Add project root (and src/ if used) to path for `import app`
project_root = Path(__file__).resolve().parents[1]
if (project_root / "src" / "app").is_dir():
    sys.path.insert(0, str(project_root / "src"))
else:
    sys.path.insert(0, str(project_root))

def _app_pkg_root(pr: Path) -> Path:
    if (pr / "src" / "app").is_dir():
        return pr / "src" / "app"
    return pr / "app"

_APP_PKG = _app_pkg_root(project_root)

from app.core.settings import DATABASE_URL


def parse_db_url(url: str):
    """Parse DATABASE_URL into components."""
    # Remove asyncpg driver prefix if present
    url_clean = url.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urlparse(url_clean)
    # URL decode password in case it has special characters
    password = unquote(parsed.password) if parsed.password else None
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/"),
        "user": parsed.username,
        "password": password,
        "url": url_clean,  # Keep full URL for alternative method
    }


def backup_postgresql(db_info, backup_file):
    """Backup PostgreSQL database using pg_dump."""
    print(f"📦 Backing up PostgreSQL database: {db_info['database']}")
    
    # Method 1: Try with PGPASSWORD environment variable
    env = os.environ.copy()
    if db_info["password"]:
        env["PGPASSWORD"] = db_info["password"]
    
    cmd = [
        "pg_dump",
        "-h", db_info["host"],
        "-p", str(db_info["port"]),
        "-U", db_info["user"],
        "-d", db_info["database"],
        "-F", "c",  # Custom format (compressed)
        "-f", str(backup_file),
    ]
    
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        file_size = backup_file.stat().st_size / (1024 * 1024)  # MB
        print(f"   ✓ Database backup created: {file_size:.2f} MB")
        return True
    except FileNotFoundError:
        print("   ❌ ERROR: pg_dump not found. Install PostgreSQL client tools.")
        print("      Ubuntu/Debian: sudo apt-get install postgresql-client")
        return False
    except subprocess.CalledProcessError as e:
        # Method 2: Try with connection string (more reliable for special chars)
        print("   ⚠ Trying alternative connection method...")
        try:
            # Use connection URI directly (handles special chars better)
            cmd2 = [
                "pg_dump",
                db_info["url"],  # Use full connection string
                "-F", "c",
                "-f", str(backup_file),
            ]
            result = subprocess.run(
                cmd2,
                capture_output=True,
                text=True,
                check=True
            )
            file_size = backup_file.stat().st_size / (1024 * 1024)  # MB
            print(f"   ✓ Database backup created: {file_size:.2f} MB")
            return True
        except subprocess.CalledProcessError as e2:
            print(f"   ❌ ERROR: pg_dump failed with both methods")
            print(f"   First error: {e.stderr[:200]}")
            print(f"   Second error: {e2.stderr[:200]}")
            print(f"\n   💡 Tip: Try manually:")
            print(f"      PGPASSWORD='your_password' pg_dump -h {db_info['host']} -U {db_info['user']} -d {db_info['database']} -F c -f {backup_file}")
            return False


def backup_sqlite(db_path, backup_file):
    """Backup SQLite database by copying file."""
    print(f"📦 Backing up SQLite database: {db_path}")
    try:
        shutil.copy2(db_path, backup_file)
        file_size = backup_file.stat().st_size / (1024 * 1024)  # MB
        print(f"   ✓ Database backup created: {file_size:.2f} MB")
        return True
    except Exception as e:
        print(f"   ❌ ERROR: SQLite backup failed: {e}")
        return False


def backup_json_files(backup_dir):
    """Backup important JSON files."""
    print("\n📄 Backing up JSON files...")
    
    json_files = [
        "data/user_state.json",
        "data/admin_sessions.json",
        "data/admin_session_state.json",
        "data/admin_ui_settings.json",
        "data/admin_ip_whitelist.json",
        "data/allowed_users.json",
        "core/plans.json",
        "core/charge_packages.json",
        "core/plans_layout.json",
        "core/charge_plans_layout.json",
    ]
    
    backed_up = 0
    for rel in json_files:
        src = _APP_PKG / rel
        arc_name = f"app/{rel}"
        if src.exists():
            dst = backup_dir / arc_name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            backed_up += 1
            print(f"   ✓ {arc_name}")
    
    print(f"   ✓ Backed up {backed_up} JSON files")
    return backed_up


def backup_env_safe(backup_dir):
    """Backup .env file but mask sensitive values."""
    print("\n🔐 Backing up .env (masked)...")
    
    env_files = [
        project_root / "config" / ".env",
        project_root / ".env",
    ]
    
    for env_file in env_files:
        if env_file.exists():
            backup_file = backup_dir / "env_masked.txt"
            try:
                with open(env_file, "r") as f:
                    lines = f.readlines()
                
                masked_lines = []
                sensitive_keys = [
                    "PASSWORD", "SECRET", "TOKEN", "KEY", "HASH",
                    "PASARGUARD_PASSWORD", "BOT_TOKEN", "ADMIN_BOT_TOKEN"
                ]
                
                for line in lines:
                    masked = line
                    if "=" in line and not line.strip().startswith("#"):
                        key = line.split("=")[0].strip()
                        if any(sk in key.upper() for sk in sensitive_keys):
                            masked = f"{key}=***MASKED***\n"
                    masked_lines.append(masked)
                
                with open(backup_file, "w") as f:
                    f.writelines(masked_lines)
                
                print(f"   ✓ Backed up {env_file.name} (secrets masked)")
                return True
            except Exception as e:
                print(f"   ⚠ Failed to backup .env: {e}")
    
    print("   ⚠ No .env file found")
    return False


def create_backup_info(backup_dir, db_info, db_type):
    """Create backup info file."""
    info = {
        "timestamp": datetime.now().isoformat(),
        "database_type": db_type,
        "database_name": db_info.get("database", "unknown"),
        "backup_files": [f.name for f in backup_dir.rglob("*") if f.is_file()],
    }
    
    info_file = backup_dir / "backup_info.json"
    with open(info_file, "w") as f:
        json.dump(info, f, indent=2)
    
    print(f"\n📋 Backup info saved: {info_file.name}")


async def backup_database():
    """Main backup function."""
    if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL not set in config/.env")
        sys.exit(1)
    
    # Parse output directory
    output_dir = Path("backups")
    if "--output-dir" in sys.argv:
        idx = sys.argv.index("--output-dir")
        if idx + 1 < len(sys.argv):
            output_dir = Path(sys.argv[idx + 1])
    
    # Create timestamped backup folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = output_dir / f"backup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("💾 DATABASE BACKUP")
    print("=" * 60)
    print(f"Backup directory: {backup_dir}")
    print()
    
    # Determine database type
    db_type = "unknown"
    db_info = {}
    backup_success = False
    
    if "postgresql" in DATABASE_URL.lower():
        db_type = "postgresql"
        db_info = parse_db_url(DATABASE_URL)
        backup_file = backup_dir / "database.dump"
        backup_success = backup_postgresql(db_info, backup_file)
    elif "sqlite" in DATABASE_URL.lower():
        db_type = "sqlite"
        # Extract SQLite path
        db_path = DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
        if not os.path.isabs(db_path):
            db_path = project_root / db_path
        else:
            db_path = Path(db_path)
        
        db_info = {"database": str(db_path)}
        backup_file = backup_dir / "database.db"
        backup_success = backup_sqlite(db_path, backup_file)
    else:
        print(f"⚠️  Unknown database type: {DATABASE_URL[:50]}...")
        print("   Skipping database backup")
    
    # Backup JSON files
    json_count = backup_json_files(backup_dir)
    
    # Backup .env (masked)
    backup_env_safe(backup_dir)
    
    # Create backup info
    create_backup_info(backup_dir, db_info, db_type)
    
    print("\n" + "=" * 60)
    if backup_success:
        print("✅ Backup complete!")
    else:
        print("⚠️  Backup completed with warnings (check above)")
    print("=" * 60)
    print(f"\nBackup location: {backup_dir}")
    print("\nTo restore:")
    print(f"  python scripts/restore_db.py {backup_dir}")
    
    return backup_success


if __name__ == "__main__":
    success = asyncio.run(backup_database())
    sys.exit(0 if success else 1)

