#!/usr/bin/env python3
"""Quick test to verify password and hash"""
import sys
sys.path.insert(0, '/root/ASSTROO')

from app.core.settings import verify_admin_password, ADMIN_PANEL_PASSWORD_HASH
import getpass

print("Current hash from .env:")
print(f"  {ADMIN_PANEL_PASSWORD_HASH}\n")

print("Enter the password you're trying to use:")
password = getpass.getpass("Password: ")

result = verify_admin_password(password, ADMIN_PANEL_PASSWORD_HASH)

if result:
    print("\n✅ Password is CORRECT - something else is wrong")
else:
    print("\n❌ Password is WRONG - that's why login is failing")
    print("\nThis means:")
    print("1. You might be using the wrong password")
    print("2. The hash might have been corrupted during copy/paste")
    print("\nSolution: Use the old SHA-256 hash temporarily, then re-migrate")

