# Quick Start Guide - Microservices API Gateway

## 30-Second Setup

### 1. Install Dependencies (Each Service)

```powershell
cd admin_portal
pipenv install

cd ..\decision_service
pipenv install

cd ..\bettor_service
pipenv install

cd ..\unity_gameplay_service
pipenv install

cd ..\bettor_analytics_service
pipenv install

cd ..\odds_generator_service
pipenv install

cd ..\bettors_bet_data_service
pipenv install
```

### 2. Run Migrations

```powershell
cd admin_portal
python manage.py migrate

cd ..\decision_service
python manage.py migrate
# ... repeat for each service
```

### 3. Start Services (Use 7 Different Powershell Windows)

**Window 1 - Admin Portal (Gateway)**

```powershell
cd admin_portal
python manage.py runserver 8006
```

**Window 2 - Decision Service**

```powershell
cd decision_service
python manage.py runserver 8000
```

**Window 3 - Unity Gameplay**

```powershell
cd unity_gameplay_service
python manage.py runserver 8001
```

**Window 4 - Bettor Service**

```powershell
cd bettor_service
python manage.py runserver 8002
```

**Window 5 - Analytics Service**

```powershell
cd bettor_analytics_service
python manage.py runserver 8003
```

**Window 6 - Bet Data Service**

```powershell
cd bettors_bet_data_service
python manage.py runserver 8004
```

**Window 7 - Odds Generator**

```powershell
cd odds_generator_service
python manage.py runserver 8005
```

---

## 🎯 Test the API Gateway

### 1. Get Admin JWT Token

```powershell
# Create admin user first
cd admin_portal
python manage.py createsuperuser

# Login via web browser
# Open: http://localhost:8006/admin/login/
# Then get token at: http://localhost:8006/sso/token/
```

### 2. List Services

```powershell
curl -X GET http://localhost:8006/api/
```

### 3. Check Service Health

```powershell
curl -X GET http://localhost:8006/api/gateway/decision/health/
curl -X GET http://localhost:8006/api/gateway/bettor/health/
```

### 4. Access API Docs

- **Admin Portal Swagger**: http://localhost:8006/api/docs/
- **Decision Service Swagger**: http://localhost:8000/api/docs/
- **Bettor Service Swagger**: http://localhost:8002/api/docs/

### 5. Get Bets from Decision Service (via Gateway)

```powershell
# Without auth (will fail)
curl -X GET http://localhost:8006/api/decision/bets/realtime/

# With JWT token
$token = "YOUR_JWT_TOKEN_HERE"
curl -X GET `
  -H "Authorization: Bearer $token" `
  http://localhost:8006/api/decision/bets/realtime/
```

---

## 📊 System Architecture

```
Your Browser
    ↓
NGINX (Port 80)
    ↓
Admin Portal (8006) ← API Gateway
    ↓
┌─────────────────────────────┐
│ Microservices (8000-8005)   │
├─────────────────────────────┤
│ Decision (8000)             │
│ Gameplay (8001)             │
│ Bettor (8002)               │
│ Analytics (8003)            │
│ Bet Data (8004)             │
│ Odds Generator (8005)       │
└─────────────────────────────┘
```

---

## 🔑 Default Credentials

- **Admin Username**: Admin portal user you created
- **JWT Secret**: `shared-secret-change-me` (⚠️ CHANGE IN PRODUCTION)
- **Database**: PostgreSQL (or SQLite for development)

---

## ✨ What's Available Now

✅ SSO Token Management  
✅ API Gateway in admin_portal  
✅ REST Framework on all services  
✅ Swagger API Documentation  
✅ Service Health Checks  
✅ Request Forwarding  
✅ Authentication Middleware

---

## 🚀 Next Steps

1. **Add API Endpoints** for each service app
2. **Connect Frontend** to http://localhost:8006/api/
3. **Deploy** to production (update ALLOWED_HOSTS, DEBUG=False)
4. **Enable HTTPS** and update SECURE settings
5. **Add Rate Limiting** for production traffic

---

## 📞 Endpoints Cheat Sheet

```
Gateway & Admin:
GET    http://localhost:8006/api/                       List services
GET    http://localhost:8006/api/gateway/{service}/health/   Health check
GET    http://localhost:8006/api/docs/                 Swagger docs
POST   http://localhost:8006/sso/token/                Issue SSO token

Decision Service:
GET    http://localhost:8000/api/bets/                 List bets
GET    http://localhost:8000/api/bets/realtime/        Real-time data
GET    http://localhost:8000/api/rounds/current_status/ Current round
GET    http://localhost:8000/api/docs/                 Swagger docs

Other Services:
GET    http://localhost:{8001-8005}/api/docs/          Service docs
```

---

## 💡 Tips

- Use Postman or Insomnia to test APIs
- Copy JWT token to `Authorization: Bearer <token>` header
- Check browser DevTools Network tab for real requests
- Services auto-create admin users on JWT validation
- Restart a service if you change code
