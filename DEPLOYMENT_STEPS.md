# 🚀 Deploy SSPACE to Render + Supabase

## Custom Domain: studyspaceapp.in

Follow these steps exactly to deploy your app with the custom domain.

---

## Step 1: Setup Supabase Database (5 minutes)

### 1.1 Create Supabase Account & Project

```bash
# Visit: https://supabase.com/dashboard
# Sign up with GitHub (easiest) or email
```

### 1.2 Create New Project

1. Click **"New Project"**
2. **Organization**: Create or select one
3. **Project Name**: `studyspace-production`
4. **Database Password**: Generate strong password (save it!)
5. **Region**: Choose closest to India (e.g., `ap-south-1` Mumbai)
6. Click **"Create new project"** (takes ~2 minutes)

### 1.3 Get Database Connection String

1. Go to **Project Settings** (gear icon) → **Database**
2. Scroll to **Connection String** section
3. Select **"URI"** tab
4. Copy the connection string (looks like):
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
   ```
5. Replace `[YOUR-PASSWORD]` with your actual password
6. **For Python async (FastAPI)**, change `postgresql://` to `postgresql+asyncpg://`:
   ```
   postgresql+asyncpg://postgres:your-password@db.xxxxx.supabase.co:5432/postgres
   ```

### 1.4 Save This Connection String
```bash
# Save somewhere safe - you'll need it for Render
DATABASE_URL=postgresql+asyncpg://postgres:YOUR-PASSWORD@db.xxxxx.supabase.co:5432/postgres
```

---

## Step 2: Setup Upstash Redis (Optional - 3 minutes)

### 2.1 Create Upstash Account

```bash
# Visit: https://console.upstash.com
# Sign up with GitHub or email
```

### 2.2 Create Redis Database

1. Click **"Create Database"**
2. **Name**: `studyspace-cache`
3. **Type**: Regional
4. **Region**: Choose closest to India
5. Click **"Create"**

### 2.3 Get Redis URL

1. Click on your database
2. Scroll to **"REST API"** section
3. Copy **"UPSTASH_REDIS_REST_URL"**:
   ```
   redis://default:YOUR-PASSWORD@region.upstash.io:PORT
   ```

### 2.4 Save This URL
```bash
REDIS_URL=redis://default:YOUR-PASSWORD@region.upstash.io:PORT
```

---

## Step 3: Setup Gmail for Emails (5 minutes)

### 3.1 Enable 2-Factor Authentication

1. Go to your Google Account: https://myaccount.google.com
2. **Security** → Enable **2-Step Verification**

### 3.2 Generate App Password

1. **Security** → **2-Step Verification** → Scroll down → **App passwords**
2. Click **"Select app"** → Choose **"Mail"**
3. Click **"Select device"** → Choose **"Other"** → Type "StudySpace"
4. Click **"Generate"**
5. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)

### 3.3 Save Credentials
```bash
mail_username=your-email@gmail.com
mail_password=abcd efgh ijkl mnop  # (without spaces: abcdefghijklmnop)
```

---

## Step 4: Prepare Your Code (2 minutes)

### 4.1 Add Health Check Endpoint

Check if this exists in `backend/app/main.py`:

```python
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

If not, add it after the CORS setup.

### 4.2 Update CORS for Production

In `backend/app/main.py`, update CORS origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Development
        "http://localhost:3000",
        "https://studyspace-frontend.onrender.com",  # Render URL
        "https://studyspaceapp.in",  # Your domain
        "https://www.studyspaceapp.in",  # WWW version
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 4.3 Commit and Push to GitHub

```bash
cd /Users/arjunkm/Study-Space

# Add all files
git add .

# Commit
git commit -m "Add Render deployment configuration"

# Push to GitHub (create repo if needed)
git push origin main
```

**If you don't have a GitHub repo yet:**
```bash
# Create new repo on GitHub: https://github.com/new
# Name it: Study-Space

# Then:
git remote add origin https://github.com/YOUR-USERNAME/Study-Space.git
git branch -M main
git push -u origin main
```

---

## Step 5: Deploy to Render (10 minutes)

### 5.1 Create Render Account

```bash
# Visit: https://dashboard.render.com/register
# Sign up with GitHub (recommended) - it will find your repos automatically
```

### 5.2 Deploy Backend

1. Click **"New +"** → **"Web Service"**
2. **Connect your GitHub repository**: `Study-Space`
3. **Basic Configuration**:
   - **Name**: `studyspace-backend`
   - **Region**: Singapore (or closest to your users)
   - **Branch**: `main`
   - **Root Directory**: (leave empty)
   - **Runtime**: `Python 3`
   - **Build Command**: `cd backend && pip install -r requirements.txt`
   - **Start Command**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

4. **Plan**: Select **"Free"** (spins down after 15min inactivity)

5. **Environment Variables** - Click "Advanced" → Add these:

   ```
   DATABASE_URL = postgresql+asyncpg://postgres:YOUR-PASSWORD@db.xxxxx.supabase.co:5432/postgres
   SECRET_KEY = [Click "Generate" button]
   ALGORITHM = HS256
   ACCESS_TOKEN_EXPIRE_MINUTES = 10080
   ENVIRONMENT = production
   REDIS_URL = redis://default:YOUR-PASSWORD@region.upstash.io:PORT
   mail_username = your-email@gmail.com
   mail_password = your-16-char-app-password
   mail_from = StudySpace <noreply@studyspaceapp.in>
   mail_server = smtp.gmail.com
   mail_port = 587
   RAZORPAY_KEY_ID = your_razorpay_key_id
   RAZORPAY_KEY_SECRET = your_razorpay_secret
   ```

6. Click **"Create Web Service"**

7. **Wait for deployment** (5-10 minutes)
   - You'll see build logs
   - Once deployed, note your backend URL: `https://studyspace-backend.onrender.com`

### 5.3 Initialize Database

Once backend is deployed:

1. Go to your backend service dashboard
2. Click **"Shell"** tab (top right)
3. Run database initialization:
   ```bash
   cd backend
   python scripts/init_db.py
   ```

### 5.4 Deploy Frontend

1. Click **"New +"** → **"Static Site"**
2. **Connect repository**: `Study-Space` (same repo)
3. **Basic Configuration**:
   - **Name**: `studyspace-frontend`
   - **Branch**: `main`
   - **Root Directory**: (leave empty)
   - **Build Command**: `cd frontend && npm install && npm run build`
   - **Publish Directory**: `frontend/dist`

4. **Environment Variables**:
   ```
   VITE_API_BASE_URL = https://studyspace-backend.onrender.com
   ```

5. Click **"Create Static Site"**

6. **Wait for deployment** (3-5 minutes)
   - Note your frontend URL: `https://studyspace-frontend.onrender.com`

---

## Step 6: Setup Custom Domain (studyspaceapp.in)

### 6.1 Configure Frontend Domain

1. Go to your **studyspace-frontend** service in Render
2. Click **"Settings"** tab
3. Scroll to **"Custom Domain"** section
4. Click **"Add Custom Domain"**
5. Enter:
   - `studyspaceapp.in`
   - `www.studyspaceapp.in`

### 6.2 Get DNS Records from Render

Render will show you DNS records like:
```
Type: A
Name: @
Value: 216.24.57.1

Type: CNAME
Name: www
Value: studyspace-frontend.onrender.com
```

### 6.3 Update DNS Settings

1. **Login to your domain registrar** (where you bought studyspaceapp.in)
   - GoDaddy, Namecheap, Google Domains, etc.

2. **Go to DNS Management**

3. **Add/Update these records**:

   **For root domain (studyspaceapp.in):**
   ```
   Type: A
   Host: @
   Value: 216.24.57.1  (or IP from Render)
   TTL: 3600
   ```

   **For www subdomain:**
   ```
   Type: CNAME
   Host: www
   Value: studyspace-frontend.onrender.com
   TTL: 3600
   ```

4. **Save changes**

### 6.4 Wait for DNS Propagation

- DNS changes can take 1-48 hours (usually 15-30 minutes)
- Check status: https://dnschecker.org

### 6.5 Configure API Subdomain (api.studyspaceapp.in)

**Optional but recommended:**

1. Go to **studyspace-backend** service in Render
2. **Settings** → **Custom Domain**
3. Add: `api.studyspaceapp.in`
4. Get the DNS record from Render
5. Add to your domain registrar:
   ```
   Type: CNAME
   Host: api
   Value: studyspace-backend.onrender.com
   TTL: 3600
   ```

6. Update frontend environment variable:
   ```
   VITE_API_BASE_URL = https://api.studyspaceapp.in
   ```

---

## Step 7: Update CORS After Domain Setup

### 7.1 Update Backend CORS

Once your domain is live, update CORS in `backend/app/main.py`:

```python
allow_origins=[
    "http://localhost:5173",
    "https://studyspace-frontend.onrender.com",
    "https://studyspaceapp.in",
    "https://www.studyspaceapp.in",
    "https://api.studyspaceapp.in",
]
```

### 7.2 Push Changes

```bash
git add .
git commit -m "Update CORS for custom domain"
git push
```

Render will auto-deploy the changes!

---

## Step 8: Test Your Deployment

### 8.1 Test Backend API

```bash
# Test health endpoint
curl https://studyspace-backend.onrender.com/health

# Should return: {"status":"healthy"}
```

### 8.2 Test Frontend

Visit: https://studyspace-frontend.onrender.com

### 8.3 Test Custom Domain

Visit: https://studyspaceapp.in

---

## Step 9: Enable HTTPS (SSL)

Render automatically provides free SSL certificates!

### 9.1 Check SSL Status

1. In Render dashboard → Your frontend service
2. Go to **Settings** → **Custom Domain**
3. You'll see SSL status for each domain
4. Wait for "SSL Certificate Issued" (takes a few minutes)

### 9.2 Force HTTPS

The SSL is automatic - all HTTP traffic redirects to HTTPS!

---

## 🎉 You're Live!

Your app is now deployed at:
- **Frontend**: https://studyspaceapp.in
- **Backend API**: https://studyspace-backend.onrender.com (or https://api.studyspaceapp.in)
- **API Docs**: https://studyspace-backend.onrender.com/docs

---

## 📊 Free Tier Limits

**Render Free Tier:**
- ✅ 750 hours/month (enough for 1 service)
- ✅ Spins down after 15 min inactivity
- ✅ Takes 30-50 seconds to wake up on first request
- ✅ Unlimited static sites

**Supabase Free Tier:**
- ✅ 500MB database storage
- ✅ Unlimited API requests
- ✅ 2GB bandwidth
- ✅ 50,000 monthly active users

**Upstash Redis Free Tier:**
- ✅ 250MB storage
- ✅ 10,000 requests/day

---

## 🔧 Post-Deployment Tasks

### Setup Monitoring

1. **Uptime Monitoring** (Free):
   - Visit: https://uptimerobot.com
   - Add monitor for: `https://studyspaceapp.in`
   - Ping every 14 minutes (keeps backend awake!)

2. **Error Tracking**: 
   - Sentry.io (free tier)

### Regular Backups

```bash
# Backup Supabase database
# In Supabase dashboard: Database → Backups (automatic daily)
```

### Update Environment Variables

If you need to change any env vars:
1. Render Dashboard → Service → Environment
2. Update variable
3. Click "Save Changes" (auto-redeployes)

---

## 🚨 Troubleshooting

### Backend won't start
```bash
# Check logs in Render dashboard
# Common issues:
# - Wrong DATABASE_URL format (must use postgresql+asyncpg://)
# - Missing environment variables
# - Python dependencies missing in requirements.txt
```

### Frontend shows "API Error"
```bash
# Check VITE_API_BASE_URL in frontend environment
# Make sure it matches your backend URL
# Check CORS settings in backend
```

### Database connection fails
```bash
# Verify DATABASE_URL format:
# postgresql+asyncpg://postgres:PASSWORD@db.xxxxx.supabase.co:5432/postgres

# Test connection from Render Shell:
python -c "from app.database import engine; print('Connected!')"
```

### Domain not working
```bash
# Check DNS propagation: https://dnschecker.org
# Verify DNS records in your registrar
# Wait 1-2 hours for DNS to propagate
# Check SSL certificate status in Render dashboard
```

---

## 💰 Cost Breakdown

**Current Setup (Free Tier):**
```
Render Backend: $0/month (Free)
Render Frontend: $0/month (Free)
Supabase Database: $0/month (Free tier)
Upstash Redis: $0/month (Free tier)
Domain (studyspaceapp.in): ~₹500-800/year (~$6-10/year)

Total: $0/month + domain cost
```

**When to Upgrade:**
- Backend spindown becomes annoying → Upgrade to Render Starter ($7/month)
- Database > 500MB → Upgrade Supabase to Pro ($25/month)
- Redis > 10K requests/day → Upgrade Upstash ($0.20/100K requests)

---

## 📞 Support

- **Render Docs**: https://render.com/docs
- **Supabase Docs**: https://supabase.com/docs
- **Render Community**: https://community.render.com
- **Supabase Discord**: https://discord.supabase.com

---

## ✅ Deployment Checklist

- [ ] Supabase project created
- [ ] Database URL saved
- [ ] Upstash Redis created (optional)
- [ ] Gmail App Password generated
- [ ] Code pushed to GitHub
- [ ] Backend deployed on Render
- [ ] Database initialized
- [ ] Frontend deployed on Render
- [ ] Custom domain DNS configured
- [ ] SSL certificate issued
- [ ] CORS updated for domain
- [ ] Tested all functionality
- [ ] Uptime monitoring setup

---

**Need help? Feel free to ask!** 🚀
