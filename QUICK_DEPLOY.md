# 🚀 Quick Start: Deploy to Render + Supabase

## Your Domain: studyspaceapp.in

---
BD34WPF1F1RZG5BJVMZDHLPT

## ⏱️ Total Time: ~30 minutes

### ✅ Phase 1: Setup Services (15 min)

**1. Create Database (5 min)**

**Option A: Render PostgreSQL (Recommended)**
- [ ] In Render dashboard → New + → PostgreSQL
- [ ] Name: `study-space-db`
- [ ] Plan: Free
- [ ] Copy "Internal Database URL"
- [ ] Change `postgresql://` to `postgresql+asyncpg://`

**Option B: Supabase (Requires IPv4 add-on)**
- [ ] Go to https://supabase.com → Sign up
- [ ] Create project: `studyspace-production`
- [ ] Region: Mumbai (ap-south-1)
- [ ] Enable IPv4 add-on (paid)
- [ ] Copy connection URL from Settings → Database
- [ ] Change `postgresql://` to `postgresql+asyncpg://`

**2. Create Upstash Redis (3 min) - Optional**
- [ ] Go to https://console.upstash.com → Sign up
- [ ] Create database: `studyspace-cache`
- [ ] Copy Redis URL
redis-cli --tls -u redis://default:AamuAAIncDIxNWFkN2Y4OGIxNGQ0ZmU0YmI5MjVjNjZkY2E0ODg3MXAyNDM0Mzg@alert-mantis-43438.upstash.io:6379

**3. Setup Gmail App Password (5 min)**
- [ ] Enable 2FA on Gmail
- [ ] Generate App Password: https://myaccount.google.com/apppasswords
- [ ] Save the 16-character password

**4. Get Razorpay Keys (2 min)**
- [ ] Login to Razorpay Dashboard
- [ ] Copy Test/Live Key ID and Secret

---

### ✅ Phase 2: Prepare Code (5 min)

**1. Update and Push Code**
```bash
cd /Users/arjunkm/Study-Space

# Check status
git status

# Add all changes
git add .

# Commit
git commit -m "Ready for Render deployment with studyspaceapp.in"

# Push to GitHub
git push origin main
```

**If you don't have GitHub repo:**
```bash
# Create repo on GitHub first: https://github.com/new
# Then:
git remote add origin https://github.com/YOUR-USERNAME/Study-Space.git
git branch -M main
git push -u origin main
```

---

### ✅ Phase 3: Deploy to Render (10 min)

**1. Deploy Backend (5 min)**
- [ ] Go to https://dashboard.render.com → Sign up with GitHub
- [ ] New + → Web Service → Connect your repo
- [ ] Name: `studyspace-backend`
- [ ] Runtime: Python 3
- [ ] Build: `cd backend && pip install -r requirements.txt`
- [ ] Start: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- [ ] Plan: **Free**
- [ ] Add environment variables (see below)
- [ ] Click "Create Web Service"
- [ ] Wait for deployment (~5 min)
- [ ] Note URL: `https://studyspace-backend.onrender.com`
- [ ] Database tables are automatically created on startup!

**Environment Variables for Backend:**
```
DATABASE_URL = postgresql+asyncpg://postgres:YOUR-PASSWORD@db.xxxxx.supabase.co:5432/postgres
SECRET_KEY = [Click Generate button]
ALGORITHM = HS256
ACCESS_TOKEN_EXPIRE_MINUTES = 10080
ENVIRONMENT = production
REDIS_URL = redis://default:YOUR-PASSWORD@region.upstash.io:PORT
mail_username = your-email@gmail.com
mail_password = your-16-char-app-password
mail_from = StudySpace <noreply@studyspaceapp.in>
mail_server = smtp.gmail.com
mail_port = 587
RAZORPAY_KEY_ID = your_key_id
RAZORPAY_KEY_SECRET = your_secret
```

**2. Deploy Frontend (5 min)**
- [ ] New + → Static Site → Connect same repo
- [ ] Name: `studyspace-frontend`
- [ ] Build: `cd frontend && npm install && npm run build`
- [ ] Publish: `frontend/dist`
- [ ] Add environment variable:
  ```
  VITE_API_BASE_URL = https://studyspace-backend.onrender.com
  ```
- [ ] Click "Create Static Site"
- [ ] Wait for deployment (~3 min)

---

### ✅ Phase 4: Configure Domain (10 min)

**1. Add Custom Domain in Render**
- [ ] Go to studyspace-frontend → Settings → Custom Domain
- [ ] Add: `studyspaceapp.in`
- [ ] Add: `www.studyspaceapp.in`
- [ ] Copy DNS records shown by Render

**2. Update DNS at Your Registrar**

Login to where you bought studyspaceapp.in and add:

```
Type: A
Name: @
Value: 216.24.57.1  (or IP shown by Render)
TTL: 3600

Type: CNAME  
Name: www
Value: studyspace-frontend.onrender.com
TTL: 3600
```

studyspace-frontend.onrender.com
studyspace-frontend.onrender.com
216.24.57.1

**Optional: API Subdomain**
- [ ] In studyspace-backend → Settings → Custom Domain
- [ ] Add: `api.studyspaceapp.in`
- [ ] Add DNS record:
  ```
  Type: CNAME
  Name: api
  Value: studyspace-backend.onrender.com
  ```
- [ ] Update frontend env: `VITE_API_BASE_URL = https://api.studyspaceapp.in`

**3. Wait for DNS & SSL**
- [ ] Wait 15-30 minutes for DNS propagation
- [ ] Check: https://dnschecker.org
- [ ] SSL certificate will be auto-issued by Render

---

### ✅ Phase 5: Test Everything (5 min)

**Test Checklist:**
- [ ] Backend health: `curl https://studyspace-backend.onrender.com/health`
- [ ] API docs: https://studyspace-backend.onrender.com/docs
- [ ] Frontend loads: https://studyspace-frontend.onrender.com
- [ ] Custom domain: https://studyspaceapp.in
- [ ] User registration works
- [ ] User login works
- [ ] Database connection works

---

## 🎉 Done! Your App is Live

**Your URLs:**
- 🌐 **Main Site**: https://studyspaceapp.in
- 🔧 **API**: https://studyspace-backend.onrender.com
- 📚 **API Docs**: https://studyspace-backend.onrender.com/docs

---

## 📊 What You're Using (All Free!)

```
✅ Render Backend: Free tier (spins down after 15min)
✅ Render Frontend: Free tier (always on)
✅ Supabase Database: 500MB free
✅ Upstash Redis: 250MB free
✅ SSL Certificates: Free (automatic)
✅ Domain: studyspaceapp.in (~₹500/year)

Total Monthly Cost: ₹0 ($0) 💰
```

---

## ⚠️ Free Tier Notes

**Backend Spin Down:**
- After 15 minutes of inactivity, backend sleeps
- First request takes 30-50 seconds to wake up
- Subsequent requests are fast

**To Keep Backend Awake:**
- Use UptimeRobot (free): https://uptimerobot.com
- Ping `https://studyspace-backend.onrender.com/health` every 14 minutes

---

## 🔄 To Update Your App

```bash
# Make changes to your code
git add .
git commit -m "Your changes"
git push

# Render automatically redeploys! 🚀
# Takes 3-5 minutes
```

---

## 🆘 Troubleshooting

**Backend won't start?**
```bash
# Check logs in Render dashboard
# Verify DATABASE_URL uses postgresql+asyncpg://
# Check all environment variables are set
```

**Frontend shows API error?**
```bash
# Check VITE_API_BASE_URL is correct
# Check CORS settings in backend
# Check backend is running
```

**Domain not working?**
```bash
# Check DNS propagation: https://dnschecker.org
# Verify DNS records at your registrar
# Wait up to 24 hours for full propagation
# Check SSL certificate status in Render
```

---

## 📞 Need Help?

- Full guide: See [DEPLOYMENT_STEPS.md](DEPLOYMENT_STEPS.md)
- Render Docs: https://render.com/docs
- Supabase Docs: https://supabase.com/docs

---

**Happy Deploying! 🎊**
