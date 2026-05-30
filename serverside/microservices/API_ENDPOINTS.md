# API Endpoints Reference

## Admin Portal - API Gateway (Port 8006)

### Gateway Management

```
GET  /api/
     Response: { services: [...], version: "1.0" }
     Description: Lists all available microservices

GET  /api/gateway/{service_id}/health/
     service_id: decision, gameplay, bettor, analytics, betdata, odds
     Response: { service, status: "healthy|unhealthy", url }
     Description: Check if a microservice is running
```

### Authentication (Portal)

```
GET  /sso/token/
     Requires: User logged in
     Response: { token: "jwt_token" }
     Cookie: admin_jwt=jwt_token
     Description: Issue new SSO JWT token for API clients

GET  /admin/
     Description: Django Admin interface
     Requires: SSO Authentication

GET  /admin/login/
     Description: Admin login page
```

### Swagger Documentation

```
GET  /api/docs/
     Description: Interactive Swagger API documentation

GET  /api/redoc/
     Description: ReDoc API documentation

GET  /api/schema/
     Description: OpenAPI 3.0 JSON schema
```

---

## Decision Service (Port 8000)

### Bets API

```
GET  /api/bets/
     Response: [{ id, player_id, amount, status, created_at }, ...]
     Description: List all bets

GET  /api/bets/{id}/
     Response: { id, player_id, amount, status, created_at }
     Description: Get specific bet details

GET  /api/bets/realtime/
     Response: { total_bets, timestamp }
     Description: Get real-time betting statistics

GET  /api/bets/recent/
     Response: [{ last 10 bets }]
     Description: Get 10 most recent bets

GET  /api/bets/{id}/detail/
     Response: { full bet object }
     Description: Get detailed bet information
```

### Rounds API

```
GET  /api/rounds/
     Response: { message, available_endpoints }
     Description: List available round endpoints

GET  /api/rounds/current_status/
     Response: {
       round_id: 1,
       status: "active",
       time_remaining: 120,
       total_bets: int,
       active_characters: int,
       timestamp: "2024-..."
     }
     Description: Get current round information

GET  /api/round/timer/  [LEGACY]
     Response: { round_id, time_remaining, status, timestamp }
     Description: Get round timer information
```

### Legacy Endpoints (Backward Compatible)

```
GET  /api/bets/phase-summary/
     Response: {
       total_decisions: int,
       results: { decision: count, ... },
       timestamp
     }
     Description: Get summary of bet decisions by phase

GET  /api/bets/realtime/  [LEGACY]
     Same as GET /api/bets/realtime/ above
```

### Documentation

```
GET  /api/docs/
     Description: Swagger documentation for Decision Service

GET  /api/redoc/
     Description: ReDoc documentation

GET  /api/schema/
     Description: OpenAPI JSON schema
```

---

## Bettor Service (Port 8002)

### Currently Available

```
GET  /admin/
     Description: Django admin interface (requires SSO)

GET  /api/docs/
     Description: Swagger documentation
```

### To Be Implemented

```
GET  /api/bettors/
     Description: List all bettors
POST /api/bettors/
     Description: Create new bettor
GET  /api/bettors/{id}/
     Description: Get specific bettor
PUT  /api/bettors/{id}/
     Description: Update bettor
DELETE /api/bettors/{id}/
     Description: Delete bettor
POST /api/activity
     Body: { eventType, metadata }
     Description: Track authenticated bettor activity for analytics
```

---

## Unity Gameplay Service (Port 8001)

### Currently Available

```
GET  /admin/
     Description: Django admin interface (requires SSO)

GET  /game/
     Description: Unity WebGL build entry point

GET  /api/docs/
     Description: Swagger documentation
```

### To Be Implemented

```
GET  /api/gameplay/state/
     Description: Get current game state
POST /api/gameplay/action/
     Description: Send player action
GET  /api/gameplay/players/
     Description: List active players
WS   /ws/gameplay/
     Description: WebSocket for real-time updates
```

---

## Bettor Analytics Service (Port 8003)

### Currently Available

```
GET  /admin/
     Description: Django admin interface (requires SSO)

GET  /api/docs/
     Description: Swagger documentation
```

### To Be Implemented

```
GET  /api/analytics/dashboard/
     Description: Analytics dashboard data
GET  /api/analytics/bettor/{bettor_id}/
     Description: Get bettor analytics
GET  /api/analytics/trends/
     Description: Get betting trends
GET  /api/analytics/reports/
     Description: Generate analytics reports
```

---

## Bet Data Service (Port 8004)

### Currently Available

```
GET  /admin/
     Description: Django admin interface (requires SSO)

GET  /api/docs/
     Description: Swagger documentation
```

### To Be Implemented

```
GET  /api/betdata/
     Description: List all bet data
GET  /api/betdata/{id}/
     Description: Get specific bet data record
POST /api/betdata/
     Description: Create bet data record
PUT  /api/betdata/{id}/
     Description: Update bet data
DELETE /api/betdata/{id}/
     Description: Delete bet data
```

---

## Odds Generator Service (Port 8005)

### Currently Available

```
GET  /admin/
     Description: Django admin interface (requires SSO)

GET  /api/docs/
     Description: Swagger documentation
```

### To Be Implemented

```
GET  /api/odds/current/
     Description: Get current odds
POST /api/odds/calculate/
     Description: Calculate odds for given parameters
GET  /api/odds/history/
     Description: Get historical odds data
PUT  /api/odds/{id}/
     Description: Update specific odds
```

---

## Request Headers

### Required Headers

```
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

### Expected Headers (Optional)

```
Accept: application/json
X-Requested-With: XMLHttpRequest
```

### Injected by Gateway

```
X-Forwarded-For: {client_ip}
X-Forwarded-Proto: {http|https}
Authorization: Bearer {sso_token}  (if not provided)
```

---

## Response Status Codes

```
200 OK              - Request successful
201 Created         - Resource created successfully
204 No Content      - Request successful, no response body
400 Bad Request     - Invalid request parameters
401 Unauthorized    - Missing or invalid authentication
403 Forbidden       - Authenticated but not authorized
404 Not Found       - Resource not found
500 Internal Error  - Server error
502 Bad Gateway     - Microservice unreachable
503 Unavailable     - Service temporarily unavailable
504 Timeout         - Request timeout (gateway)
```

---

## Authentication Flow

### 1. Get Token (SSO)

```powershell
# Login via web interface
http://localhost:8006/admin/login/

# Get token
curl http://localhost:8006/sso/token/
```

### 2. Use Token

```powershell
# Set header
$headers = @{
    "Authorization" = "Bearer eyJhbGciOiJIUzI1NiIs..."
}

# Make request
curl -H $headers http://localhost:8000/api/bets/
```

### 3. Token Refresh

```
- Token TTL: 3600 seconds (default)
- Refresh: Automatic via middleware
- Cookie: admin_jwt (secure, HttpOnly)
```

---

## Example Usage

### Get List of Bets

```powershell
$token = "YOUR_JWT_TOKEN"
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

$response = Invoke-WebRequest `
    -Uri "http://localhost:8006/api/decision/bets/" `
    -Headers $headers
$response.Content | ConvertFrom-Json
```

### Create Bet (Future)

```powershell
$token = "YOUR_JWT_TOKEN"
$body = @{
    player_id = 123
    amount = 100.00
} | ConvertTo-Json

$response = Invoke-WebRequest `
    -Uri "http://localhost:8006/api/decision/bets/" `
    -Method POST `
    -Headers @{"Authorization" = "Bearer $token"} `
    -Body $body
```

### Health Check

```powershell
$response = Invoke-WebRequest `
    -Uri "http://localhost:8006/api/gateway/decision/health/"
$response.Content | ConvertFrom-Json
```

---

## Rate Limiting (Future)

Currently no rate limiting. To be implemented:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1623456789
```

---

## Field Validation Rules

```
player_id:      integer, > 0
bet_amount:     decimal, 0.01 - 999999.99
status:         enum: [pending, accepted, rejected, settled]
round_id:       integer, > 0
created_at:     ISO 8601 datetime (read-only)
updated_at:     ISO 8601 datetime (read-only)
```
