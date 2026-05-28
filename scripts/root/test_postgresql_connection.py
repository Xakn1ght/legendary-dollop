#!/usr/bin/env python3
"""Quick test of PostgreSQL connection"""

import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test_connection():
    # Your connection details
    db_name = "yomastrbot_db"
    db_user = "astronaut_admin"
    db_password = "6Y33zY!W@sHer39"
    db_host = "localhost"
    db_port = "5432"
    
    pg_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    print(f"Testing connection to: {db_host}:{db_port}/{db_name}")
    print(f"User: {db_user}")
    print("")
    
    try:
        engine = create_async_engine(pg_url, echo=False)
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version(), current_database(), current_user"))
            row = result.fetchone()
            print("✅ Connection successful!")
            print(f"   PostgreSQL version: {row[0].split(',')[0]}")
            print(f"   Database: {row[1]}")
            print(f"   User: {row[2]}")
            return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check if PostgreSQL is running: sudo systemctl status postgresql")
        print("2. Check if port 5432 is listening: sudo netstat -tlnp | grep 5432")
        print("3. Try connecting directly: sudo -u postgres psql -d yomastrbot_db")
        return False
    finally:
        try:
            await engine.dispose()
        except:
            pass

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
