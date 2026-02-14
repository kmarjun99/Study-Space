# Connecting to PostgreSQL (Production Grade)

The backend code is now fully upgraded to support PostgreSQL using the high-performance `asyncpg` driver.

## 1. Get a Database
We recommend **Supabase** or **Neon** for a managed PostgreSQL instance (Free Tier is excellent).

1. Go to [Supabase](https://supabase.com/).
2. Create a new Project.
3. Go to **Project Settings** -> **Database**.
4. Copy the **Connection String** (URI Mode). It will look like:
   `postgresql://postgres.xxxx:password@aws-0-region.pooler.supabase.com:6543/postgres`

## 2. Update .env
Open `backend/.env` and replace the `DATABASE_URL` with your new connection string.
**Important**: For the async driver, changing the protocol from `postgresql://` to `postgresql+asyncpg://` is usually required.

Example `backend/.env`:
```env
# OLD (SQLite)
# DATABASE_URL=sqlite+aiosqlite:///./study_space.db

# NEW (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://postgres.your-user:your-password@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
SECRET_KEY=your_secure_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## 3. Restart
Run `.\start_backend.bat`. The app will automatically connect to Postgres and create all tables.

## 4. Why this is superior?
- **Concurrent Bookings**: No more "Database Locked" errors.
- **Scalable**: Handles thousands of connections.
- **PostGIS Ready**: Ready for future geo-spatial features (Maps).
