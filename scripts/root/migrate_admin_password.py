#!/usr/bin/env python3
"""
Admin Password Migration Script
================================

This script helps you migrate your admin password hash from SHA-256 to Argon2.

Usage:
    python migrate_admin_password.py

The script will:
1. Check your current password hash format
2. If it's SHA-256, help you generate a new Argon2 hash
3. Provide the new hash to update in your .env file

Note: Password migration also happens automatically on your next successful login.
"""

import os
import sys
import getpass
from dotenv import load_dotenv

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

from app.core.settings import (
    ADMIN_PANEL_PASSWORD_HASH,
    generate_password_hash,
    needs_password_migration,
    verify_admin_password,
    is_sha256_hash,
    is_argon2_hash,
)


def main():
    print("\n" + "="*70)
    print("🔐 Admin Password Migration Tool - SHA-256 to Argon2")
    print("="*70 + "\n")
    
    # Load environment
    load_dotenv()
    
    if not ADMIN_PANEL_PASSWORD_HASH:
        print("❌ No ADMIN_PANEL_PASSWORD_HASH found in .env file")
        print("\nTo set up a new password:")
        print("  from app.api.routes.admin_auth import setup_admin_password")
        print("  setup_admin_password('your_password')")
        return
    
    # Check current hash format
    print(f"Current hash: {ADMIN_PANEL_PASSWORD_HASH[:20]}...")
    
    if is_argon2_hash(ADMIN_PANEL_PASSWORD_HASH):
        print("✅ Your password is already using Argon2 (secure)")
        print("   No migration needed!")
        return
    
    if is_sha256_hash(ADMIN_PANEL_PASSWORD_HASH):
        print("⚠️  Your password is using SHA-256 (legacy)")
        print("   Migration to Argon2 is recommended for better security\n")
    else:
        print("❌ Unknown hash format")
        return
    
    # Ask for password to verify and migrate
    print("To migrate your password, please enter your current password:")
    password = getpass.getpass("Password: ")
    
    if not password:
        print("❌ Password cannot be empty")
        return
    
    # Verify the password
    print("\nVerifying password...")
    if not verify_admin_password(password, ADMIN_PANEL_PASSWORD_HASH):
        print("❌ Password verification failed")
        print("   Please make sure you entered the correct password")
        return
    
    print("✅ Password verified successfully\n")
    
    # Generate new Argon2 hash
    print("Generating new Argon2 hash...")
    new_hash = generate_password_hash(password)
    
    print("\n" + "="*70)
    print("✅ Migration Complete!")
    print("="*70)
    print("\nYour new Argon2 password hash has been generated.")
    print("Please update your .env file with the following:\n")
    print(f"ADMIN_PANEL_PASSWORD_HASH={new_hash}")
    print("\n" + "="*70)
    print("\n⚠️  Important: After updating .env, restart your application")
    print("   for the changes to take effect.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

