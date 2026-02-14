# SSPACE - Study Space Management Platform 🎓

> A modern, production-ready web application for managing study spaces, accommodations, and room bookings.

## 🚀 Tech Stack

**Backend:**
- FastAPI (Python 3.11+)
- PostgreSQL / SQLite
- SQLAlchemy (Async ORM)
- JWT Authentication

**Frontend:**
- React 19 + TypeScript
- Vite
- React Router v7
- Axios

**DevOps:**
- Docker & Docker Compose
- Nginx
- CI/CD Ready

---

## 📁 Project Structure

```
SSPACE/
├── backend/                 # Python FastAPI Backend
│   ├── app/
│   │   ├── core/           # Core configuration
│   │   ├── models/         # Database models
│   │   ├── routers/        # API endpoints
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   ├── middleware/     # Custom middleware
│   │   └── utils/          # Utilities
│   ├── scripts/            # Database scripts
│   ├── tests/              # Backend tests
│   └── migrations/         # Database migrations
│
├── frontend/               # React TypeScript Frontend
│   ├── src/
│   │   ├── components/    # UI components
│   │   ├── pages/         # Page components
│   │   ├── services/      # API services
│   │   ├── hooks/         # Custom hooks
│   │   └── utils/         # Utilities
│   └── public/            # Static assets
│
├── docs/                  # Documentation
│   ├── ARCHITECTURE.md    # System architecture
│   ├── DEVELOPMENT.md     # Dev setup guide
│   ├── DEPLOYMENT.md      # Production deployment
│   └── API.md             # API documentation
│
└── docker-compose.yml     # Container orchestration
```

---

## 🏃 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (optional)

### Option 1: Docker (Recommended)

```bash
# Start all services
docker-compose up --build

# Access:
# Frontend: http://localhost
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Option 2: Manual Setup

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env

# Run server
uvicorn app.main:app --reload
```

Backend runs at: **http://localhost:8000**

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Setup environment
cp .env.example .env

# Run dev server
npm run dev
```

Frontend runs at: **http://localhost:5173**

---

## 📚 Documentation

- **[Architecture Overview](docs/ARCHITECTURE.md)** - System design and structure
- **[Development Guide](docs/DEVELOPMENT.md)** - Local setup and development
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment
- **[API Documentation](docs/API.md)** - API endpoints and usage

---

## �� Features

### For Students
- Browse accommodations and study spaces
- Book rooms and manage reservations
- View availability and pricing
- Leave reviews and ratings

### For Venue Owners
- List properties and spaces
- Manage bookings and calendar
- Track payments and revenue
- Respond to inquiries

### For Administrators
- User management
- Content moderation
- Analytics dashboard
- System configuration

---

## 🚀 Production Ready

This project includes:
- ✅ Clean, modular architecture
- ✅ Docker containerization
- ✅ Production-ready configuration
- ✅ Comprehensive documentation
- ✅ Type safety (TypeScript + Pydantic)
- ✅ Security best practices
- ✅ API documentation
- ✅ Database migrations
- ✅ Environment-based configuration
- ✅ Ready for CI/CD

---

## 📊 API Documentation

Interactive API documentation available at:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

See [docs/API.md](docs/API.md) for detailed endpoint documentation.

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

---

**Made with ❤️ by the SSPACE Team**
