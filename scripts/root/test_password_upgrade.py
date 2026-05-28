#!/usr/bin/env python3
"""
Test Script for Password Hash Upgrade (SHA-256 to Argon2)
==========================================================

This script tests the password hashing upgrade to ensure:
1. New Argon2 hashes work correctly
2. Old SHA-256 hashes still work (backwards compatibility)
3. Hash type detection works properly
4. Migration detection works correctly
"""

import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(__file__))

from app.core.settings import (
    hash_admin_password,
    hash_admin_password_sha256,
    verify_admin_password,
    generate_password_hash,
    needs_password_migration,
    is_sha256_hash,
    is_argon2_hash,
)


def test_hash_detection():
    """Test hash format detection"""
    print("\n" + "="*70)
    print("Test 1: Hash Format Detection")
    print("="*70)
    
    # Test SHA-256 detection
    sha256_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    print(f"SHA-256 hash: {sha256_hash[:20]}...")
    assert is_sha256_hash(sha256_hash), "Failed to detect SHA-256 hash"
    assert not is_argon2_hash(sha256_hash), "Incorrectly detected as Argon2"
    print("✅ SHA-256 detection works")
    
    # Test Argon2 detection
    argon2_hash = "$argon2id$v=19$m=65536,t=3,p=4$somesalt$somehash"
    print(f"Argon2 hash: {argon2_hash[:30]}...")
    assert is_argon2_hash(argon2_hash), "Failed to detect Argon2 hash"
    assert not is_sha256_hash(argon2_hash), "Incorrectly detected as SHA-256"
    print("✅ Argon2 detection works")
    
    print("✅ All hash detection tests passed\n")


def test_argon2_hashing():
    """Test Argon2 hashing and verification"""
    print("="*70)
    print("Test 2: Argon2 Hashing")
    print("="*70)
    
    password = "TestPassword123!"
    
    # Generate Argon2 hash
    print(f"Hashing password: {password}")
    hash1 = hash_admin_password(password)
    print(f"Hash generated: {hash1[:50]}...")
    
    assert is_argon2_hash(hash1), "Generated hash is not Argon2 format"
    print("✅ Generated hash is in Argon2 format")
    
    # Verify correct password
    assert verify_admin_password(password, hash1), "Failed to verify correct password"
    print("✅ Correct password verified successfully")
    
    # Verify incorrect password
    assert not verify_admin_password("WrongPassword", hash1), "Incorrectly verified wrong password"
    print("✅ Wrong password correctly rejected")
    
    # Test that same password generates different hashes (salt)
    hash2 = hash_admin_password(password)
    assert hash1 != hash2, "Same password generated identical hashes (salt not working)"
    assert verify_admin_password(password, hash2), "Second hash doesn't verify"
    print("✅ Salt working correctly (different hashes for same password)")
    
    print("✅ All Argon2 hashing tests passed\n")


def test_sha256_compatibility():
    """Test SHA-256 backwards compatibility"""
    print("="*70)
    print("Test 3: SHA-256 Backwards Compatibility")
    print("="*70)
    
    password = "LegacyPassword456!"
    
    # Generate legacy SHA-256 hash
    print(f"Generating legacy SHA-256 hash for: {password}")
    legacy_hash = hash_admin_password_sha256(password)
    print(f"Legacy hash: {legacy_hash}")
    
    assert is_sha256_hash(legacy_hash), "Generated hash is not SHA-256 format"
    print("✅ Generated hash is in SHA-256 format")
    
    # Verify that verify_admin_password works with legacy hash
    assert verify_admin_password(password, legacy_hash), "Failed to verify password with legacy hash"
    print("✅ Legacy SHA-256 hash verified successfully")
    
    # Verify incorrect password
    assert not verify_admin_password("WrongPassword", legacy_hash), "Incorrectly verified wrong password"
    print("✅ Wrong password correctly rejected with legacy hash")
    
    print("✅ All SHA-256 compatibility tests passed\n")


def test_migration_detection():
    """Test migration detection"""
    print("="*70)
    print("Test 4: Migration Detection")
    print("="*70)
    
    # Test SHA-256 hash needs migration
    sha256_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert needs_password_migration(sha256_hash), "Failed to detect SHA-256 needs migration"
    print("✅ SHA-256 hash correctly detected as needing migration")
    
    # Test Argon2 hash doesn't need migration
    argon2_hash = "$argon2id$v=19$m=65536,t=3,p=4$somesalt$somehash"
    assert not needs_password_migration(argon2_hash), "Incorrectly detected Argon2 needs migration"
    print("✅ Argon2 hash correctly detected as not needing migration")
    
    # Test empty hash
    assert not needs_password_migration(""), "Empty hash detected as needing migration"
    print("✅ Empty hash handled correctly")
    
    print("✅ All migration detection tests passed\n")


def test_generate_password_hash():
    """Test password hash generation helper"""
    print("="*70)
    print("Test 5: Password Hash Generation Helper")
    print("="*70)
    
    password = "AdminPassword789!"
    
    # Generate hash using helper function
    print(f"Generating hash for: {password}")
    hash_value = generate_password_hash(password)
    print(f"Generated hash: {hash_value[:50]}...")
    
    # Should be Argon2
    assert is_argon2_hash(hash_value), "Generated hash is not Argon2 format"
    print("✅ Helper generates Argon2 hash")
    
    # Should verify correctly
    assert verify_admin_password(password, hash_value), "Generated hash doesn't verify"
    print("✅ Generated hash verifies correctly")
    
    print("✅ All hash generation tests passed\n")


def test_mixed_scenario():
    """Test real-world mixed scenario"""
    print("="*70)
    print("Test 6: Real-World Mixed Scenario")
    print("="*70)
    
    password = "MySecurePassword2024!"
    
    # Simulate existing SHA-256 hash (legacy)
    print("Scenario: User has legacy SHA-256 hash")
    legacy_hash = hash_admin_password_sha256(password)
    print(f"  Legacy hash: {legacy_hash}")
    
    # Verify login with legacy hash
    assert verify_admin_password(password, legacy_hash), "Login failed with legacy hash"
    print("✅ Login successful with legacy hash")
    
    # Detect migration needed
    assert needs_password_migration(legacy_hash), "Failed to detect migration needed"
    print("✅ System detected migration needed")
    
    # Generate new Argon2 hash
    new_hash = generate_password_hash(password)
    print(f"  New hash: {new_hash[:50]}...")
    
    # Verify login with new hash
    assert verify_admin_password(password, new_hash), "Login failed with new hash"
    print("✅ Login successful with new Argon2 hash")
    
    # Verify no migration needed for new hash
    assert not needs_password_migration(new_hash), "New hash incorrectly flagged for migration"
    print("✅ New hash doesn't need further migration")
    
    print("✅ Real-world scenario test passed\n")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("🔐 Password Hash Upgrade Test Suite")
    print("="*70)
    print("Testing SHA-256 to Argon2 migration...")
    
    try:
        test_hash_detection()
        test_argon2_hashing()
        test_sha256_compatibility()
        test_migration_detection()
        test_generate_password_hash()
        test_mixed_scenario()
        
        print("="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nThe password hash upgrade is working correctly!")
        print("- Argon2 hashing: ✅")
        print("- SHA-256 backwards compatibility: ✅")
        print("- Migration detection: ✅")
        print("- Hash format detection: ✅")
        print("\nYou can safely deploy this upgrade.\n")
        
        return 0
        
    except AssertionError as e:
        print("\n" + "="*70)
        print("❌ TEST FAILED")
        print("="*70)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    except Exception as e:
        print("\n" + "="*70)
        print("❌ UNEXPECTED ERROR")
        print("="*70)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

