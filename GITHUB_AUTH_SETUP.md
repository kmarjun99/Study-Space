# GitHub Authentication Setup Guide

## The Error You're Seeing:
```
remote: Invalid username or token. Password authentication is not supported
```

This happens because GitHub disabled password authentication in 2021. You need to use a **Personal Access Token (PAT)** instead.

---

## ✅ Solution: Create Personal Access Token (5 minutes)

### Step 1: Generate Token on GitHub

1. **Go to:** https://github.com/settings/tokens/new

2. **Fill in:**
   - **Note**: `Study-Space Deployment` (or any name you like)
   - **Expiration**: Choose `90 days` or `No expiration`
   - **Select scopes** (check these boxes):
     - ✅ `repo` (Full control of private repositories)
     - ✅ `workflow` (Update GitHub Actions workflows)

3. **Click** "Generate token" at the bottom

4. **IMPORTANT**: Copy the token (starts with `ghp_...`)
   - ⚠️ You won't be able to see it again!
   - Save it somewhere safe temporarily

### Step 2: Push Using Token

Run this command:
```bash
git push -u origin main
```

When prompted:
- **Username**: `kmarjun99`
- **Password**: Paste your token (ghp_xxxxxxxxxxxxx)

### Step 3: Cache Credentials (So you don't need to enter it every time)

After successful push, run:
```bash
# On macOS (stores in Keychain)
git config --global credential.helper osxkeychain

# Verify it's set
git config --global credential.helper
```

Now you won't need to enter the token again!

---

## 🔐 Alternative: Use SSH (More Secure, One-time Setup)

### If you prefer SSH authentication:

**Step 1: Check for existing SSH key**
```bash
ls -la ~/.ssh
# Look for id_rsa.pub or id_ed25519.pub
```

**Step 2: Generate new SSH key (if needed)**
```bash
ssh-keygen -t ed25519 -C "your-email@example.com"
# Press Enter to accept default location
# Press Enter twice for no passphrase (or set one)
```

**Step 3: Copy your SSH public key**
```bash
cat ~/.ssh/id_ed25519.pub
# Copy the entire output
```

**Step 4: Add to GitHub**
1. Go to: https://github.com/settings/ssh/new
2. Title: `MacBook Pro`
3. Paste your public key
4. Click "Add SSH key"

**Step 5: Change remote URL to SSH**
```bash
git remote set-url origin git@github.com:kmarjun99/Study-Space.git
git push -u origin main
```

---

## 🚀 Quick Summary

**Easiest Method (Use Personal Access Token):**
```bash
# 1. Create token: https://github.com/settings/tokens/new
# 2. Push and use token as password:
git push -u origin main
# Username: kmarjun99
# Password: [paste your token]

# 3. Cache credentials:
git config --global credential.helper osxkeychain
```

---

## ❓ Troubleshooting

**"Still asking for password every time"**
```bash
# Make sure credential helper is set
git config --global credential.helper osxkeychain
```

**"SSH key already exists"**
```bash
# Just add it to GitHub: https://github.com/settings/ssh/new
cat ~/.ssh/id_ed25519.pub  # Copy and paste
```

**"Permission denied (publickey)"**
```bash
# Test SSH connection
ssh -T git@github.com
# Should say: "Hi kmarjun99! You've successfully authenticated"
```

---

## 📌 What to Do Next

1. ✅ Create Personal Access Token: https://github.com/settings/tokens/new
2. ✅ Run: `git push -u origin main` (use token as password)
3. ✅ Run: `git config --global credential.helper osxkeychain`
4. ✅ Ready to deploy to Render!

---

Need help? Let me know which method you'd like to use!
