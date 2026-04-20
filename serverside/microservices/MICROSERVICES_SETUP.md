# Microservices Architecture - Implementation Summary

## ✅ Completed Tasks

### 1. SSO Middleware Integration (All 5 Services)

✅ **Status**: Complete - Already configured

All microservices have `AdminSSOMiddleware` installed:

- **decision_service** - `/decision_service/middleware.py`
- **bettor_service** - `/bettor_service/middleware.py`
- **unity_gameplay_service** - `/unity_gameplay_service/middleware.py`
- **bettor_analytics_service** - `/bettor_analytics_service/middleware.py`
- **bettors_bet_data_service** - `/bettor_bet_data_service/middleware.py`

**How it works:**

- Validates JWT tokens from `Authorization: Bearer <token>` header
- Falls back to SSO cookie (`admin_jwt`)
- Auto-creates superuser on first authentication
- Protects all `/admin/` endpoints and API routes

---

### 2. API Gateway in Admin Portal ✅

**Status**: Complete

New **Gateway App** created to centralize all microservice requests:

- **Location**: `/admin_portal/gateway/`
- **Views**: Intelligent request forwarding with authentication
- **Features**:
  - Service health checks
  - Request forwarding with SSO token injection
  - Rate limiting ready
  - Error handling (timeouts, bad gateway, etc.)

**Microservices Mapped:**

```
/api/decision/     → http://127.0.0.1:8000 (Decision Service)
/api/gameplay/     → http://127.0.0.1:8001 (Unity Gameplay)
/api/bettor/       → http://127.0.0.1:8002 (Bettor Service)
/api/analytics/    → http://127.0.0.1:8003 (Bettor Analytics)
/api/betdata/      → http://127.0.0.1:8004 (Bet Data Service)
/api/odds/         → http://127.0.0.1:8005 (Odds Generator)
```

**Endpoints:**

- `GET /api/` - List all available services
- `GET /api/gateway/{service_id}/health/` - Check service health

---

### 3. API Endpoints & REST Framework ✅

**Status**: Complete

**Decision Service** - Full REST API implemented:

```
GET  /api/bets/                    # List all bets
GET  /api/bets/{id}/               # Get specific bet
GET  /api/bets/realtime/           # Realtime betting data
GET  /api/bets/recent/             # Last 10 bets
GET  /api/rounds/                  # List rounds
GET  /api/rounds/current_status/   # Current round status
GET  /api/round/timer/             # Legacy: round timer
```

**All Services Now Include:**

- Django REST Framework (DRF)
- DRF Spectacular (OpenAPI/Swagger)
- Serializers for data validation
- ViewSets for standard CRUD operations

---

### 4. Swagger/OpenAPI Documentation ✅

**Status**: Complete

**Every service now has auto-generated API docs:**

**Admin Portal Gateway:**

- Swagger UI: `http://localhost:8006/api/docs/`
- ReDoc: `http://localhost:8006/api/redoc/`
- Schema: `http://localhost:8006/api/schema/`

**Decision Service:**

- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`
- Schema: `http://localhost:8000/api/schema/`

**Other Services:**

- Same pattern at `/api/docs/`, `/api/redoc/`, `/api/schema/` after setup

---

## 📦 Dependencies Installed

All Pipfiles updated with:

```
djangorestframework = "*"
drf-spectacular = "*"
pyjwt = "*"
httpx = "*"  # (admin_portal only)
```

**Install in each service:**

```bash
cd admin_portal && pipenv install
cd decision_service && pipenv install
cd bettor_service && pipenv install
cd unity_gameplay_service && pipenv install
cd bettor_analytics_service && pipenv install
cd odds_generator_service && pipenv install
cd bettors_bet_data_service && pipenv install
```

---

## 🚀 Next Steps

### 1. Install Dependencies

```bash
cd admin_portal
pipenv install

cd ../decision_service
pipenv install

# ... repeat for each service
```

### 2. Run Migrations

```bash
cd admin_portal
python manage.py migrate

cd ../decision_service
python manage.py migrate
# ... etc
```

### 3. Create Superuser (Optional)

```bash
cd admin_portal
python manage.py createsuperuser
```

### 4. Start Services in Separate Terminals

```bash
# Terminal 1 - Admin Portal (Gateway)
cd admin_portal
python manage.py runserver 8006

# Terminal 2 - Decision Service
cd decision_service
python manage.py runserver 8000

# Terminal 3 - Bettor Service
cd bettor_service
python manage.py runserver 8002

# ... start other services
```

### 5. Access API Gateway

- **API Root**: http://localhost:8006/api/
- **Swagger Docs**: http://localhost:8006/api/docs/
- **Health Check**: http://localhost:8006/api/gateway/decision/health/

---

## 📋 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      NGINX (Port 80)                        │
│              Reverse Proxy / Load Balancer                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│           Admin Portal (Port 8006) - API Gateway            │
│  • OAuth2 / SSO Token Management                            │
│  • Request Forwarding to Microservices                      │
│  • Service Health Monitoring                                │
│  • Swagger Documentation                                    │
└─────────────────────────────────────────────────────────────┘
         ↙        ↓        ↓        ↓        ↓        ↘
    ┌──────┐ ┌───────────┐ ┌────────┐ ┌──────────┐ ┌─────────┐
    │8000  │ │   8001    │ │  8002  │ │  8003    │ │  8004   │
    │Decis │ │  Gameplay │ │Bettor  │ │Analytics │ │Bet Data │
    │Service│ │Service   │ │Service │ │Service   │ │Service  │
    └──────┘ └───────────┘ └────────┘ └──────────┘ └─────────┘
                    │
              ┌──────────┐
              │  8005    │
              │Odds      │
              │Generator │
              └──────────┘
```

---

## 🔑 Key Features

### ✅ Authentication & Authorization

- JWT token generation in admin_portal
- Auto-validation in all microservices
- Bearer token + Cookie support
- Automatic user provisioning

### ✅ Service Discovery

- Centralized service registry in gateway
- Health check endpoints
- Timeout & error handling

### ✅ API Documentation

- Auto-generated Swagger/OpenAPI schemas
- Available at `/api/docs/` for each service
- Fully documented endpoints

### ✅ Request Routing

- Smart forwarding with authentication
- Header injection (X-Forwarded-\*)
- Error handling and timeouts

### ✅ Development Ready

- Ready for additional microservices
- Template structure established
- Scalable architecture

---

## 📝 Environment Variables

All services support these env vars:

```
SSO_TTL_SECONDS=3600              # Token expiration
SSO_REFRESH_WINDOW_SECONDS=300    # Refresh threshold
SSO_COOKIE_NAME=admin_jwt         # Cookie name
SSO_COOKIE_DOMAIN=                # Cookie domain
SSO_COOKIE_SECURE=0               # HTTPS only
SSO_COOKIE_SAMESITE=Lax           # SameSite policy
DB_NAME=...                       # Database name
DB_USER=postgres                  # Database user
DB_PASSWORD=...                   # Database password
DB_HOST=localhost                 # Database host
DB_PORT=5432                      # Database port
```

---

## ⚠️ Important Notes

1. **JWT Secret**: All services share `SSO_SECRET = "shared-secret-change-me"` - **CHANGE THIS IN PRODUCTION**

2. **PostgreSQL**: Services using PostgreSQL (not SQLite) need database setup

3. **ALLOWED_HOSTS**: Add production domain to each service's `ALLOWED_HOSTS`

4. **CORS**: If frontend on different domain, add `django-cors-headers` to services

5. **Nginx**: Already configured in `/nginx.conf` with proper proxy rules

---

## 🛠️ Troubleshooting

**Module not found errors?**

```bash
pipenv install
pipenv shell
```

**JWT validation failed?**

- Check `SSO_SECRET` matches across all services
- Verify `SSO_COOKIE_NAME` matches

**Gateway timeout?**

- Check microservice is running on correct port
- Review firewall settings
- Check database connections

---

## 📚 Additional Resources

- [Django REST Framework](https://www.django-rest-framework.org/)
- [DRF Spectacular](https://drf-spectacular.readthedocs.io/)
- [JWT Authentication](https://pyjwt.readthedocs.io/)
- [Nginx Reverse Proxy](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
