#!/usr/bin/env python3
"""
Database restore script - Restores from a backup.

Usage:
    python scripts/restore_db.py backups/backup_20240101_120000 [--confirm]

This script will:
1. Restore PostgreSQL database (pg_restore)
2. Restore SQLite database (copy file)
3. Restore JSON files
"""

import asyncio
import sys
import os
import subprocess
import shutil
from pathlib import Path
from urllib.parse import urlparse, unquote

# Add project root (and src/ if used) to path
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
    url_clean = url.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urlparse(url_clean)
    password = unquote(parsed.password) if parsed.password else None
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/"),
        "user": parsed.username,
        "password": password,
        "url": url_clean,
    }


def restore_postgresql(db_info, backup_file):
    """Restore PostgreSQL database using pg_restore."""
    print(f"📦 Restoring PostgreSQL database: {db_info['database']}")
    
    # Method 1: Try with PGPASSWORD environment variable
    env = os.environ.copy()
    if db_info["password"]:
        env["PGPASSWORD"] = db_info["password"]
    
    cmd = [
        "pg_restore",
        "-h", db_info["host"],
        "-p", str(db_info["port"]),
        "-U", db_info["user"],
        "-d", db_info["database"],
        "-c",  # Clean (drop) before restore
        str(backup_file),
    ]
    
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        print("   ✓ Database restored")
        return True
    except FileNotFoundError:
        print("   ❌ ERROR: pg_restore not found. Install PostgreSQL client tools.")
        return False
    except subprocess.CalledProcessError as e:
        # Method 2: Try with connection string
        print("   ⚠ Trying alternative connection method...")
        try:
            cmd2 = [
                "pg_restore",
                "-d", db_info["url"],  # Use full connection string
                "-c",
                str(backup_file),
            ]
            result = subprocess.run(
                cmd2,
                capture_output=True,
                text=True,
                check=True
            )
            print("   ✓ Database restored")
            return True
        except subprocess.CalledProcessError as e2:
            print(f"   ❌ ERROR: pg_restore failed with both methods")
            print(f"   Error: {e2.stderr[:200]}")
            return False


def restore_sqlite(db_path, backup_file):
    """Restore SQLite database by copying file."""
    print(f"📦 Restoring SQLite database: {db_path}")
    try:
        # Backup existing DB first
        if os.path.exists(db_path):
            shutil.copy2(db_path, f"{db_path}.old")
        
        shutil.copy2(backup_file, db_path)
        print("   ✓ Database restored")
        return True
    except Exception as e:
        print(f"   ❌ ERROR: SQLite restore failed: {e}")
        return False


def restore_json_files(backup_dir):
    """Restore JSON files from backup."""
    print("\n📄 Restoring JSON files...")
    
    json_files = [
        "app/data/user_state.json",
        "app/data/admin_sessions.json",
        "app/data/admin_session_state.json",
        "app/data/admin_ui_settings.json",
        "app/data/admin_ip_whitelist.json",
        "app/data/allowed_users.json",
        "app/core/plans.json",
        "app/core/charge_packages.json",
        "app/core/plans_layout.json",
        "app/core/charge_plans_layout.json",
    ]
    
    restored = 0
    for arc_name in json_files:
        src = backup_dir / arc_name
        if src.exists():
            rel_inside_app = Path(arc_name).relative_to("app")
            dst = _APP_PKG / rel_inside_app
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            restored += 1
            print(f"   ✓ {json_file}")
    
    print(f"   ✓ Restored {restored} JSON files")
    return restored


async def restore_database():
    """Main restore function."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/restore_db.py <backup_directory> [--confirm]")
        sys.exit(1)
    
    backup_dir = Path(sys.argv[1])
    if not backup_dir.exists():
        print(f"❌ ERROR: Backup directory not found: {backup_dir}")
        sys.exit(1)
    
    if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL not set in config/.env")
        sys.exit(1)
    
    print("=" * 60)
    print("⚠️  DATABASE RESTORE")
    print("=" * 60)
    print(f"Backup directory: {backup_dir}")
    print(f"Target database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    print("\n⚠️  WARNING: This will REPLACE all current data!")
    print("=" * 60)
    
    # Safety check
    if "--confirm" not in sys.argv:
        response = input("\nType 'RESTORE' to confirm: ")
        if response != "RESTORE":
            print("❌ Restore cancelled.")
            sys.exit(0)
    
    # Determine database type and restore
    db_type = "unknown"
    db_info = {}
    restore_success = False
    
    if "postgresql" in DATABASE_URL.lower():
        db_type = "postgresql"
        db_info = parse_db_url(DATABASE_URL)
        backup_file = backup_dir / "database.dump"
        if backup_file.exists():
            restore_success = restore_postgresql(db_info, backup_file)
        else:
            print(f"❌ Backup file not found: {backup_file}")
    elif "sqlite" in DATABASE_URL.lower():
        db_type = "sqlite"
        db_path = DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
        if not os.path.isabs(db_path):
            db_path = project_root / db_path
        else:
            db_path = Path(db_path)
        
        db_info = {"database": str(db_path)}
        backup_file = backup_dir / "database.db"
        if backup_file.exists():
            restore_success = restore_sqlite(db_path, backup_file)
        else:
            print(f"❌ Backup file not found: {backup_file}")
    else:
        print(f"⚠️  Unknown database type: {DATABASE_URL[:50]}...")
    
    # Restore JSON files
    json_count = restore_json_files(backup_dir)
    
    print("\n" + "=" * 60)
    if restore_success:
        print("✅ Restore complete!")
        print("\nNext steps:")
        print("1. Restart your bots (userbot.service, adminbot.service)")
        print("2. Verify the application")
    else:
        print("❌ Restore failed (check errors above)")
    print("=" * 60)
    
    return restore_success


if __name__ == "__main__":
    success = asyncio.run(restore_database())
    sys.exit(0 if success else 1)

