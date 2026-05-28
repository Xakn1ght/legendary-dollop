# Admin Password Migration Guide - SHA-256 to Argon2

## What Changed?

The admin authentication system has been upgraded from **SHA-256** to **Argon2** for password hashing. Argon2 is significantly more secure and resistant to brute-force attacks.

### Key Benefits of Argon2:
- **Memory-hard**: Requires significant memory to compute, making GPU attacks expensive
- **Time-cost**: Adjustable computational cost
- **Parallel-resistant**: Designed to resist parallel processing attacks
- **Industry standard**: Winner of the Password Hashing Competition (2015)

## Backwards Compatibility

✅ **Your existing passwords will continue to work!**

The system automatically detects whether a hash is:
- **Argon2 format** (starts with `$argon2`) - New secure format
- **SHA-256 format** (64 hex characters) - Legacy format

When you log in with a SHA-256 hash, the system will:
1. Verify your password using the old method
2. Automatically generate a new Argon2 hash
3. Display the new hash in the console for you to update your `.env` file

## Migration Options

### Option 1: Automatic Migration (Recommended)

Simply log in to the admin panel as usual. The system will:
1. Verify your password
2. Detect the SHA-256 hash
3. Generate a new Argon2 hash
4. Display it in the console

**Steps:**
1. Log in to admin panel with your existing password
2. Check the console output for the new hash
3. Update your `.env` file:
   ```env
   ADMIN_PANEL_PASSWORD_HASH=<new_argon2_hash>
   ```
4. Restart your application

### Option 2: Manual Migration Script

Use the provided migration script for a controlled migration:

```bash
python migrate_admin_password.py
```

The script will:
1. Check your current hash format
2. Ask for your password
3. Verify it
4. Generate the new Argon2 hash
5. Display instructions to update your `.env` file

### Option 3: Generate New Hash from Scratch

If you want to set a new password or generate a fresh hash:

```python
from app.api.routes.admin_auth import setup_admin_password

# Generate hash for your password
setup_admin_password("YourSecurePassword123!")
```

This will output:
```
============================================================
🔐 Argon2 Password Hash Generated
============================================================
Add this to your .env file:
ADMIN_PANEL_PASSWORD_HASH=$argon2id$v=19$m=65536,t=3,p=4$...
============================================================
```

## Installation

The new system requires the `passlib` library with Argon2 support:

```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install 'passlib[argon2]'
```

## Security Improvements

| Feature | SHA-256 | Argon2 |
|---------|---------|--------|
| Brute-force resistance | Medium | Very High |
| GPU attack resistance | Low | High |
| Memory requirements | Minimal | High (configurable) |
| Time cost | Fixed, fast | Adjustable, slower |
| Salt handling | Manual | Built-in |
| Industry standard | Yes | Yes (newer) |

## Hash Format Examples

**SHA-256 (Old):**
```
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```
- 64 hexadecimal characters
- Fast to compute
- Vulnerable to GPU attacks

**Argon2 (New):**
```
$argon2id$v=19$m=65536,t=3,p=4$randomsalt$hashedpassword
```
- Contains algorithm version, parameters, salt, and hash
- Slow to compute (by design)
- Resistant to modern attacks

## Troubleshooting

### Migration not triggered automatically

**Cause:** You're already using Argon2, or the hash format is not recognized.

**Solution:** Check your current hash in `.env`:
- If it's 64 hex characters → SHA-256 (will auto-migrate)
- If it starts with `$argon2` → Already Argon2 (no migration needed)

### "Password verification failed" during migration

**Cause:** The password you entered doesn't match the stored hash.

**Solution:** 
1. Make sure you're entering the correct password
2. Check that `ADMIN_PANEL_SECRET_KEY` hasn't changed (SHA-256 uses it)
3. Try logging in through the web interface first

### Application won't start after update

**Cause:** Missing `passlib` dependency.

**Solution:**
```bash
pip install 'passlib[argon2]'
```

### Old hash still in use after migration

**Cause:** You haven't updated the `.env` file with the new hash.

**Solution:**
1. Find the new hash in console output
2. Update `.env` file
3. Restart the application

## Code Changes Summary

### Modified Files

1. **`requirements.txt`**
   - Added: `passlib[argon2]`

2. **`app/core/settings/security.py`** (and related package modules under `app/core/settings/`)
   - Imported `passlib.hash.argon2`
   - Added `is_sha256_hash()` - Detect SHA-256 format
   - Added `is_argon2_hash()` - Detect Argon2 format
   - Added `hash_admin_password_sha256()` - Legacy SHA-256 hashing
   - Updated `hash_admin_password()` - Now uses Argon2
   - Updated `verify_admin_password()` - Auto-detects hash type
   - Added `needs_password_migration()` - Check if migration needed

3. **`app/api/routes/admin_auth.py`**
   - Updated security documentation
   - Added `_migrate_password_hash()` - Handle migration
   - Updated `handle_admin_login()` - Trigger migration on login
   - Updated `setup_admin_password()` - Generate Argon2 hashes

4. **New Files**
   - `migrate_admin_password.py` - Migration script
   - `ADMIN_PASSWORD_MIGRATION.md` - This guide

## Testing the Upgrade

1. **Test with existing SHA-256 hash:**
   ```bash
   # Should work and trigger migration
   curl -X POST http://localhost:8080/api/admin/login \
     -H "Content-Type: application/json" \
     -d '{"chat_id": "YOUR_ADMIN_ID", "password": "your_password"}'
   ```

2. **Check console for migration message:**
   ```
   ============================================================
   🔐 SECURITY UPDATE: Password Hash Migrated to Argon2
   ============================================================
   ```

3. **Update .env and test again:**
   - Should work without triggering migration

## FAQ

**Q: Do I need to change my password?**
A: No, only the hash format changes. Your actual password stays the same.

**Q: What happens if I don't migrate?**
A: Your old SHA-256 hash will continue to work, but won't benefit from Argon2's security improvements.

**Q: Can I roll back to SHA-256?**
A: Yes, but not recommended. Keep a backup of your old hash if needed.

**Q: How long does Argon2 hashing take?**
A: A few hundred milliseconds - imperceptible to users, but significant for attackers.

**Q: Will this affect performance?**
A: Only during login (once per session). The slight delay is a security feature.

## Support

If you encounter issues:
1. Check this guide first
2. Review console logs for error messages
3. Verify all dependencies are installed
4. Test the migration script manually

## Security Best Practices

After migration:
1. ✅ Use a strong, unique password (12+ characters)
2. ✅ Enable 2FA via Telegram (`ADMIN_2FA_ENABLED=true`)
3. ✅ Keep `ADMIN_PANEL_SECRET_KEY` secure
4. ✅ Monitor login attempts in logs
5. ✅ Update `.env` file with new hash
6. ✅ Restart application after updating

---

**Last Updated:** December 2024
**Version:** 2.0 (Argon2 Upgrade)

