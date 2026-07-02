#!/usr/bin/env python3
"""
Reset database script - DANGER: This will delete ALL data!

Usage:
    python scripts/reset_db.py [--confirm]

This script will:
1. Drop all tables
2. Re-run migrations
3. Seed initial data (star reward tiers)
4. Create indexes

WARNING: This deletes all data. Use with caution.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root (and src/ if used) to path
project_root = Path(__file__).resolve().parents[1]
if (project_root / "src" / "app").is_dir():
    sys.path.insert(0, str(project_root / "src"))
else:
    sys.path.insert(0, str(project_root))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.settings import DATABASE_URL
from app.database.models import Base, init_db
from app.database.indexes import create_all_indexes


async def drop_all_tables(engine):
    """Drop all tables from the database."""
    print("🗑️  Dropping all tables...")
    async with engine.begin() as conn:
        # Get all table names
        if "postgresql" in str(engine.url):
            # PostgreSQL
            result = await conn.execute(text("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
            """))
            tables = [row[0] for row in result.fetchall()]
        else:
            # SQLite
            result = await conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """))
            tables = [row[0] for row in result.fetchall()]
        
        if not tables:
            print("   No tables found.")
            return
        
        # Drop tables with CASCADE for PostgreSQL
        for table in tables:
            try:
                if "postgresql" in str(engine.url):
                    await conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                else:
                    await conn.execute(text(f'DROP TABLE IF EXISTS "{table}"'))
                print(f"   ✓ Dropped {table}")
            except Exception as e:
                print(f"   ⚠ Failed to drop {table}: {e}")


async def create_tables():
    """Create all tables using init_db()."""
    print("\n📦 Creating tables...")
    try:
        # Use init_db() which handles table creation properly
        await init_db()
        print("   ✓ Tables created")
    except Exception as e:
        print(f"   ⚠ Error creating tables: {e}")
        # Fallback: try direct creation
        try:
            engine = create_async_engine(DATABASE_URL, echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await engine.dispose()
            print("   ✓ Tables created (fallback method)")
        except Exception as e2:
            print(f"   ❌ Failed to create tables: {e2}")
            raise


async def seed_initial_data(session: AsyncSession):
    """No-op: the legacy star-tier system is retired (2026-06, rewards rework).

    Re-seeding it with is_active tiers would re-open the closed play->stars->credit
    money route. The Star Season engine needs no seed rows — it creates its own
    season on first use.
    """
    print("\n🌱 Seeding initial data... (nothing to seed — legacy tiers retired)")


async def create_indexes(session: AsyncSession):
    """Create database indexes."""
    print("\n📊 Creating indexes...")
    try:
        await create_all_indexes(session)
        print("   ✓ Indexes created")
    except Exception as e:
        print(f"   ⚠ Index creation warnings: {e}")


async def reset_database():
    """Main reset function."""
    if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL not set in config/.env")
        sys.exit(1)
    
    print("=" * 60)
    print("⚠️  DATABASE RESET SCRIPT")
    print("=" * 60)
    print(f"Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    print("\n⚠️  WARNING: This will DELETE ALL DATA!")
    print("=" * 60)
    
    # Safety check
    if "--confirm" not in sys.argv:
        response = input("\nType 'RESET' to confirm: ")
        if response != "RESET":
            print("❌ Reset cancelled.")
            sys.exit(0)
    
    try:
        # Create engine
        engine = create_async_engine(DATABASE_URL, echo=False)
        
        # Step 1: Drop all tables
        await drop_all_tables(engine)
        
        # Close engine before init_db (it creates its own)
        await engine.dispose()
        
        # Step 2: Create tables using init_db()
        await create_tables()
        
        # Step 3: Recreate engine for seeding and indexing
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        # Step 4: Seed initial data
        async with async_session() as session:
            await seed_initial_data(session)
        
        # Step 5: Create indexes
        async with async_session() as session:
            await create_indexes(session)
        
        # Close engine
        await engine.dispose()
        
        print("\n" + "=" * 60)
        print("✅ Database reset complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Restart your bots (userbot.service, adminbot.service)")
        print("2. Test the application")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(reset_database())

