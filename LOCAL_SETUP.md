# Local Development Setup Guide

This guide explains how to run the Stoney project on your local machine (not in Docker).

## Prerequisites

- Python 3.11 or higher
- PostgreSQL (installed locally)
- Redis (installed locally)
- Node.js 18 or higher (for client-side)
- pipenv package manager

## Step 1: Install PostgreSQL & Redis

### Windows

**PostgreSQL:**

- Download from: https://www.postgresql.org/download/windows/
- Install with default settings (default port 5432)
- Remember the password you set during installation

**Redis:**

- Download from: https://github.com/microsoftarchive/redis/releases
- Or use Windows Subsystem for Linux (WSL) and `wsl` + `apt-get install redis-server`
- Default port: 6379

### macOS

```bash
# Using Homebrew
brew install postgresql redis

# Start services
brew services start postgresql
brew services start redis
```

### Linux (Ubuntu/Debian)

```bash
# Install packages
sudo apt-get install postgresql postgresql-contrib redis-server

# Start services
sudo systemctl start postgresql
sudo systemctl start redis-server
```

## Step 2: Create Databases

Connect to PostgreSQL and create the required databases:

```sql
-- Create databases
CREATE DATABASE "DECISIONAPP";
CREATE DATABASE "CLIENTBETDATA";
CREATE DATABASE "ODDSGENERATOR";
CREATE DATABASE "DEMOMONEY";
CREATE DATABASE "BETTORS";

-- Verify
\l
```

Or use a script:

```bash
psql -U postgres -c "CREATE DATABASE \"DECISIONAPP\";"
psql -U postgres -c "CREATE DATABASE \"CLIENTBETDATA\";"
psql -U postgres -c "CREATE DATABASE \"ODDSGENERATOR\";"
psql -U postgres -c "CREATE DATABASE \"DEMOMONEY\";"
psql -U postgres -c "CREATE DATABASE \"BETTORS\";"
```

## Step 3: Setup Environment

Copy the local environment file:

```bash
cp .env.local .env.local
# Edit .env.local if needed (usually defaults to localhost work)
```

## Step 4: Install Backend Dependencies

```bash
cd serverside/microservices

# Install each service
cd admin_portal && pipenv install && cd ..
cd decision_service && pipenv install && cd ..
cd bettor_service && pipenv install && cd ..
cd bettor_analytics_service && pipenv install && cd ..
cd bettors_bet_data_service && pipenv install && cd ..
cd odds_generator_service && pipenv install && cd ..
cd unity_gameplay_service && pipenv install && cd ..
```

## Step 5: Run Database Migrations

```bash
cd serverside/microservices

# Admin Portal (runs all migrations for the gateway)
cd admin_portal
pipenv run python manage.py migrate
cd ..

# Decision Service
cd decision_service
pipenv run python manage.py migrate
cd ..

# Bettor Service
cd bettor_service
pipenv run python manage.py migrate
cd ..

# And so on for other services...
```

## Step 6: Start Backend Services

Open **separate terminal windows** for each service:

**Terminal 1 - Admin Portal (Gateway at localhost:8006)**

```bash
cd serverside/microservices/admin_portal
pipenv run python manage.py runserver 8006
```

**Terminal 2 - Decision Service (localhost:8000)**

```bash
cd serverside/microservices/decision_service
pipenv run python manage.py runserver 8000
```

**Terminal 3 - Bettor Service (localhost:8002)**

```bash
cd serverside/microservices/bettor_service
pipenv run python manage.py runserver 8002
```

**Terminal 4 - Bettor Analytics (localhost:8003)**

```bash
cd serverside/microservices/bettor_analytics_service
pipenv run python manage.py runserver 8003
```

**Terminal 5 - Bet Data Service (localhost:8004)**

```bash
cd serverside/microservices/bettors_bet_data_service
pipenv run python manage.py runserver 8004
```

**Terminal 6 - Odds Generator (localhost:8005)**

```bash
cd serverside/microservices/odds_generator_service
pipenv run python manage.py runserver 8005
```

**Terminal 7 - Unity Gameplay (localhost:8001)**

```bash
cd serverside/microservices/unity_gameplay_service
pipenv run python manage.py runserver 8001
```

## Step 7: Setup & Start Client-Side

In a **new terminal**:

```bash
cd clientside

# Install dependencies
npm install

# Copy environment config
cp .env.example .env.local

# Start the client gateway
npm start
# or
node server.js
```

The client will be available at: http://localhost:3000

## Step 8: Verify Everything Works

1. Open browser: http://localhost:3000
2. Check that characters are loaded
3. Try placing a bet
4. Check the game board updates

## Port Summary

| Service                    | Local Port | URL                   |
| -------------------------- | ---------- | --------------------- |
| Client Gateway             | 3000       | http://localhost:3000 |
| Admin Portal / API Gateway | 8006       | http://localhost:8006 |
| Decision Service           | 8000       | http://localhost:8000 |
| Unity Gameplay             | 8001       | http://localhost:8001 |
| Bettor Service             | 8002       | http://localhost:8002 |
| Bettor Analytics           | 8003       | http://localhost:8003 |
| Bet Data Service           | 8004       | http://localhost:8004 |
| Odds Generator             | 8005       | http://localhost:8005 |
| PostgreSQL                 | 5432       | localhost:5432        |
| Redis                      | 6379       | localhost:6379        |

## Troubleshooting

### "Connection refused" errors

Make sure PostgreSQL and Redis are running:

```bash
# Check PostgreSQL
psql -U postgres -c "SELECT version();"

# Check Redis
redis-cli ping
# Should return: PONG
```

### Migration errors

Make sure database exists:

```bash
psql -U postgres -l | grep DECISIONAPP
```

### Port already in use

Change the port in the service start command:

```bash
cd admin_portal
pipenv run python manage.py runserver 8007  # Use 8007 instead
```

Then update the .env.local file to match the new port.

### Module not found errors

Ensure pipenv dependencies are installed:

```bash
cd <service_directory>
pipenv install
pipenv sync
```

## Switching Between Docker and Local Development

### To use Docker:

```bash
docker compose up --build
```

### To use local development:

```bash
# Make sure .env and .env.local are configured correctly
# Then start services as shown above
```

The code automatically detects which environment you're in based on:

- For Python services: `DB_NAME` environment variable (set = Docker/local DB, unset = SQLite)
- For Node services: Environment variables pointing to localhost or Docker names
