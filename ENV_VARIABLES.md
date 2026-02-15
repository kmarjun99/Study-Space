# Environment Variables for Render Deployment

## Copy these values when deploying to Render

---

## 🔐 Backend Environment Variables

### Database Configuration
```
DATABASE_URL
Value: postgresql+asyncpg://postgres:[YOUR-SUPABASE-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
```

### Security (REQUIRED)
```
SECRET_KEY
Value: [Click "Generate" button in Render, or use: openssl rand -hex 32]

ALGORITHM
Value: HS256

ACCESS_TOKEN_EXPIRE_MINUTES
Value: 10080

ENVIRONMENT
Value: production
```

### Redis Cache (Optional)
```
REDIS_URL
Value: redis://default:[YOUR-PASSWORD]@[REGION].upstash.io:[PORT]
Or leave empty if not using Redis
```

### Email Configuration (Gmail)
```
mail_username
Value: your-email@gmail.com

mail_password  
Value: [Your 16-character Gmail App Password - no spaces]

mail_from
Value: StudySpace <noreply@studyspaceapp.in>

mail_server
Value: smtp.gmail.com

mail_port
Value: 587
```

### Payment Gateway (Razorpay)
```
RAZORPAY_KEY_ID
Value: [Your Razorpay Key ID - starts with rzp_test_ or rzp_live_]

RAZORPAY_KEY_SECRET
Value: [Your Razorpay Secret Key]
```

---

## 🎨 Frontend Environment Variables

```
VITE_API_BASE_URL
Value: https://studyspace-backend.onrender.com

Or if using custom API domain:
Value: https://api.studyspaceapp.in
```

---

## 📋 Quick Copy Template

**For Backend (copy and fill in):**
```
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres
SECRET_KEY=CLICK_GENERATE_IN_RENDER
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
ENVIRONMENT=production
REDIS_URL=redis://default:YOUR_PASSWORD@region.upstash.io:PORT
mail_username=your-email@gmail.com
mail_password=your-16-char-app-password
mail_from=StudySpace <noreply@studyspaceapp.in>
mail_server=smtp.gmail.com
mail_port=587
RAZORPAY_KEY_ID=your_key_id
RAZORPAY_KEY_SECRET=your_secret
```

**For Frontend:**
```
VITE_API_BASE_URL=https://studyspace-backend.onrender.com
```

---

## 🔑 How to Get Each Value

### 1. DATABASE_URL (Supabase)
1. Go to Supabase Dashboard → Your Project
2. Settings → Database → Connection String → URI
3. Copy and change `postgresql://` to `postgresql+asyncpg://`
4. Replace `[YOUR-PASSWORD]` with your actual password

### 2. SECRET_KEY
- Click "Generate" button in Render when adding the variable
- OR run locally: `openssl rand -hex 32`

### 3. REDIS_URL (Upstash)
1. Go to Upstash Dashboard → Your Database
2. Copy the Redis URL from the connection details
3. Format: `redis://default:password@region.upstash.io:port`

### 4. Gmail App Password
1. Enable 2FA: https://myaccount.google.com/security
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Copy the 16-character password (remove spaces)

### 5. Razorpay Keys
1. Login: https://dashboard.razorpay.com
2. Settings → API Keys
3. For testing: Use Test Keys (rzp_test_...)
4. For production: Generate Live Keys (rzp_live_...)

---

## ⚡ Adding Variables in Render

### Method 1: During Service Creation
1. When creating the service, scroll to "Environment Variables"
2. Click "Add Environment Variable"
3. Enter Key and Value
4. Repeat for all variables

### Method 2: After Service Creation
1. Go to your service dashboard
2. Click "Environment" tab on the left
3. Click "Add Environment Variable"
4. Add all variables
5. Service will automatically redeploy

---

## 🔒 Security Notes

- ✅ Never commit these values to Git
- ✅ Use different keys for test and production
- ✅ Rotate SECRET_KEY periodically
- ✅ Use Gmail App Password, not your actual password
- ✅ Keep Razorpay secrets secure

---

## 📝 Verification Checklist

After adding all variables:

- [ ] DATABASE_URL uses `postgresql+asyncpg://`
- [ ] SECRET_KEY is at least 32 characters
- [ ] mail_password is 16 characters (Gmail App Password)
- [ ] RAZORPAY keys match your dashboard
- [ ] VITE_API_BASE_URL matches your backend URL
- [ ] All required variables are set
- [ ] No typos in variable names
- [ ] Service deployed successfully

---

## 🆘 If Something's Wrong

**Backend fails to start:**
```bash
# Check logs in Render dashboard
# Common issues:
# - Wrong DATABASE_URL format
# - Missing required variables  
# - Invalid credentials
```

**To test locally first:**
```bash
# Create .env file in backend/
# Add all variables
# Run: uvicorn app.main:app --reload
# Test: curl http://localhost:8000/health
```

---

## ✨ Optional Variables (Advanced)

```
# SendGrid (alternative to Gmail)
SENDGRID_API_KEY=your_sendgrid_key

# Sentry (error tracking)
SENTRY_DSN=your_sentry_dsn

# Custom settings
MAX_UPLOAD_SIZE=10485760
CORS_ORIGINS=https://studyspaceapp.in,https://www.studyspaceapp.in
```

---

Need help? See [DEPLOYMENT_STEPS.md](DEPLOYMENT_STEPS.md) for detailed instructions.
