#!/usr/bin/env python3
"""
AstroByte Admin Password Generator

This script generates a secure password hash for the admin panel.
Run this script and add the output to your .env file.

Usage:
    python generate_admin_password.py
    
Then follow the instructions to add the hash to your .env file.
"""

import hashlib
import secrets
import getpass
import os
import sys

# Add the app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def generate_secret_key():
    """Generate a new secret key"""
    return secrets.token_hex(32)

def hash_password(password: str, secret_key: str) -> str:
    """Hash password with SHA-256 + salt"""
    salt = secret_key[:16]
    return hashlib.sha256((salt + password + salt).encode()).hexdigest()

def main():
    print("\n" + "="*60)
    print("🔐 AstroByte Admin Password Generator")
    print("="*60 + "\n")
    
    # Check if .env exists
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    env_exists = os.path.exists(env_path)
    
    # Check for existing secret key
    existing_secret = os.environ.get('ADMIN_PANEL_SECRET_KEY')
    
    if existing_secret:
        print("✓ Found existing ADMIN_PANEL_SECRET_KEY")
        secret_key = existing_secret
    else:
        print("⚠️  No ADMIN_PANEL_SECRET_KEY found. Generating new one...")
        secret_key = generate_secret_key()
        print(f"\n📝 Add this to your .env file:")
        print(f"   ADMIN_PANEL_SECRET_KEY={secret_key}\n")
    
    # Get password from user
    print("Enter your desired admin password.")
    print("💡 Tips for a strong password:")
    print("   - At least 12 characters")
    print("   - Mix uppercase, lowercase, numbers, symbols")
    print("   - Don't use common words or patterns\n")
    
    while True:
        password = getpass.getpass("Enter password: ")
        
        if len(password) < 8:
            print("❌ Password must be at least 8 characters. Try again.\n")
            continue
        
        confirm = getpass.getpass("Confirm password: ")
        
        if password != confirm:
            print("❌ Passwords don't match. Try again.\n")
            continue
        
        break
    
    # Generate hash
    password_hash = hash_password(password, secret_key)
    
    print("\n" + "="*60)
    print("✅ Password hash generated successfully!")
    print("="*60)
    print("\n📝 Add these lines to your .env file:\n")
    
    if not existing_secret:
        print(f"ADMIN_PANEL_SECRET_KEY={secret_key}")
    
    print(f"ADMIN_PANEL_PASSWORD_HASH={password_hash}")
    
    # 2FA setting
    print("\n# Optional: Disable 2FA (not recommended)")
    print("# ADMIN_2FA_ENABLED=false")
    
    print("\n" + "="*60)
    print("🔒 Security Checklist:")
    print("="*60)
    print("□ Add the above to .env file")
    print("□ Make sure .env is in .gitignore")
    print("□ Keep 2FA enabled for maximum security")
    print("□ Use HTTPS in production")
    print("□ Restart the bot after changes")
    print("="*60 + "\n")
    
    # Offer to update .env automatically
    if env_exists:
        update = input("Would you like to update .env automatically? (y/n): ").lower()
        if update == 'y':
            try:
                with open(env_path, 'r') as f:
                    content = f.read()
                
                # Check and update/add values
                lines = content.split('\n')
                new_lines = []
                found_secret = False
                found_hash = False
                
                for line in lines:
                    if line.startswith('ADMIN_PANEL_SECRET_KEY='):
                        new_lines.append(f'ADMIN_PANEL_SECRET_KEY={secret_key}')
                        found_secret = True
                    elif line.startswith('ADMIN_PANEL_PASSWORD_HASH='):
                        new_lines.append(f'ADMIN_PANEL_PASSWORD_HASH={password_hash}')
                        found_hash = True
                    else:
                        new_lines.append(line)
                
                # Add if not found
                if not found_secret:
                    new_lines.append(f'ADMIN_PANEL_SECRET_KEY={secret_key}')
                if not found_hash:
                    new_lines.append(f'ADMIN_PANEL_PASSWORD_HASH={password_hash}')
                
                with open(env_path, 'w') as f:
                    f.write('\n'.join(new_lines))
                
                print("\n✅ .env file updated successfully!")
                print("🔄 Restart the bot to apply changes.\n")
                
            except Exception as e:
                print(f"\n❌ Error updating .env: {e}")
                print("Please update manually.\n")
    else:
        print(f"⚠️  No .env file found at {env_path}")
        print("Please create one and add the values above.\n")

if __name__ == '__main__':
    main()

