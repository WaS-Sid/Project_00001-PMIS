# Environment Variables Reference

This document describes all environment variables used by the PMIS system across API, Worker, and Web components.

## Overview

Environment variables are organized by scope:
- **Database**: PostgreSQL configuration
- **Cache & Queue**: Redis and Celery settings
- **Application**: Core app settings and logging
- **LLM/AI**: Language model provider configuration
- **Integrations**: External services (email, S3, Sentry)
- **Security**: Authentication and CORS settings

---

## Database Configuration

### `POSTGRES_USER`
- **Type**: String
- **Default**: `postgres`
- **Description**: PostgreSQL database username
- **Used By**: API, Worker
- **Example**: `postgres`, `pmis_prod`

### `POSTGRES_PASSWORD`
- **Type**: String
- **Default**: `postgres`
- **Description**: PostgreSQL database password
- **Used By**: API, Worker
- **Security Risk**: HIGH - change in production
- **Example**: `Tr0pical!Monkey2024`

### `POSTGRES_DB`
- **Type**: String
- **Default**: `pmis`
- **Description**: PostgreSQL database name
- **Used By**: API, Worker
- **Example**: `pmis`, `pmis_prod`, `pmis_staging`

### `DATABASE_URL`
- **Type**: Connection String
- **Format**: `postgresql://user:password@host:port/dbname`
- **Default**: `postgresql://postgres:postgres@postgres:5432/pmis`
- **Description**: Full PostgreSQL connection string (overrides individual settings)
- **Used By**: API, Worker
- **Example**: `postgresql://postgres:secret@db.example.com:5432/pmis_prod`

---

## Cache & Queue Configuration

### `REDIS_PASSWORD`
- **Type**: String
- **Default**: None (no password)
- **Description**: Redis authentication password
- **Used By**: API, Worker
- **Security Risk**: HIGH - always set in production
- **Example**: `SecureRedispass123`

### `REDIS_URL`
- **Type**: Connection String
- **Format**: `redis://[:password]@host:port/db`
- **Default**: `redis://redis:6379/0`
- **Description**: Redis connection string for caching
- **Used By**: API, Worker
- **Example**: `redis://:SecureRedispass123@cache.example.com:6379/0`

### `CELERY_BROKER`
- **Type**: Connection String
- **Format**: `redis://[:password]@host:port/db`
- **Default**: `redis://redis:6379/0`
- **Description**: Celery message broker URL (usually Redis)
- **Used By**: Worker
- **Example**: `redis://:SecureRedispass123@cache.example.com:6379/0`

### `CELERY_RESULT_BACKEND`
- **Type**: Connection String
- **Format**: `redis://[:password]@host:port/db`
- **Default**: `redis://redis:6379/1`
- **Description**: Celery result backend for task results (separate DB from broker)
- **Used By**: Worker
- **Example**: `redis://:SecureRedispass123@cache.example.com:6379/1`

---

## Application Configuration

### `ENVIRONMENT`
- **Type**: String (enum)
- **Values**: `development`, `staging`, `production`
- **Default**: `development`
- **Description**: Application environment
- **Used By**: API, Worker, Web
- **Impact**: Affects logging, error handling, security features

### `LOG_LEVEL`
- **Type**: String (enum)
- **Values**: `debug`, `info`, `warning`, `error`, `critical`
- **Default**: `info`
- **Description**: Logging verbosity level
- **Used By**: API, Worker
- **Example**: `info` (production), `debug` (development)

### `API_HOST`
- **Type**: String
- **Default**: `0.0.0.0`
- **Description**: API server bind address
- **Used By**: API
- **Note**: Use 0.0.0.0 in containers, 127.0.0.1 for local dev

### `API_PORT`
- **Type**: Integer
- **Default**: `8000`
- **Description**: API server port
- **Used By**: API

### `API_WORKERS`
- **Type**: Integer
- **Default**: `4`
- **Description**: Number of Uvicorn worker processes
- **Used By**: API
- **Recommendation**: CPU cores * 2 + 1

---

## Web/Frontend Configuration

### `NEXT_PUBLIC_API_URL`
- **Type**: URL String
- **Default**: `http://localhost:8000/api`
- **Description**: Backend API base URL (must be accessible from browser)
- **Used By**: Web (client-side)
- **Critical**: Must be publicly accessible URL in production
- **Examples**:
  - Local: `http://localhost:8000/api`
  - Production: `https://api.yourdomain.com/api`
  - Docker: `http://api:8000/api` (service name)

### `NODE_ENV`
- **Type**: String (enum)
- **Values**: `development`, `production`
- **Default**: `development`
- **Description**: Next.js environment mode
- **Used By**: Web
- **Impact**: Enables/disables optimizations, source maps

---

## LLM & AI Configuration

Choose one provider configuration based on your AI model host.

### Azure OpenAI (Microsoft Foundry) - Recommended

#### `AZURE_OPENAI_API_KEY`
- **Type**: String (Secret)
- **Description**: Azure OpenAI API authentication key
- **Used By**: API (LangGraph)
- **Security**: Store in secrets manager, never commit

#### `AZURE_OPENAI_ENDPOINT`
- **Type**: URL String
- **Format**: `https://{resource-name}.openai.azure.com/`
- **Description**: Azure OpenAI resource endpoint
- **Example**: `https://pmis-prod.openai.azure.com/`

#### `AZURE_OPENAI_DEPLOYMENT_NAME`
- **Type**: String
- **Description**: Name of deployed model in Azure
- **Example**: `gpt-4-prod`, `gpt-35-turbo`

### OpenAI (Direct)

#### `OPENAI_API_KEY`
- **Type**: String (Secret)
- **Description**: OpenAI API key for direct API calls
- **Used By**: API (LangGraph)
- **Security**: Store in secrets manager
- **Example**: `sk-...`

### Anthropic Claude

#### `ANTHROPIC_API_KEY`
- **Type**: String (Secret)
- **Description**: Anthropic API key for Claude models
- **Used By**: API (LangGraph)
- **Security**: Store in secrets manager

---

## Optional Integrations

### Email Configuration

#### `SMTP_SERVER`
- **Type**: String
- **Default**: `smtp.gmail.com`
- **Description**: SMTP server for email ingestion
- **Used By**: Worker (email_ingest task)

#### `SMTP_PORT`
- **Type**: Integer
- **Default**: `587` (TLS), `465` (SSL)
- **Description**: SMTP server port

#### `SMTP_USERNAME`
- **Type**: String
- **Description**: SMTP authentication username

#### `SMTP_PASSWORD`
- **Type**: String (Secret)
- **Description**: SMTP authentication password
- **Security Risk**: HIGH

### AWS S3 / Cloud Storage

#### `S3_BUCKET_NAME`
- **Type**: String
- **Description**: S3 bucket for file storage
- **Example**: `pmis-production`

#### `S3_REGION`
- **Type**: String
- **Default**: `us-east-1`
- **Example**: `us-west-2`, `eu-central-1`

#### `S3_ACCESS_KEY_ID`
- **Type**: String (Secret)
- **Description**: AWS access key ID
- **Security Risk**: HIGH

#### `S3_SECRET_ACCESS_KEY`
- **Type**: String (Secret)
- **Description**: AWS secret access key
- **Security Risk**: HIGH

### Sentry (Error Tracking)

#### `SENTRY_DSN`
- **Type**: URL String
- **Description**: Sentry Data Source Name for error tracking
- **Format**: `https://examplePublicKey@o0.ingest.sentry.io/0`
- **Used By**: API, Worker

---

## Security Configuration

### `CORS_ORIGINS`
- **Type**: Comma-separated URLs
- **Default**: `*` (allow all in dev)
- **Description**: Allowed origins for CORS
- **Used By**: API
- **Production Example**: `https://yourdomain.com,https://www.yourdomain.com`

### `SECRET_KEY`
- **Type**: String (Secret)
- **Description**: JWT/session secret key
- **Length**: Minimum 32 characters recommended
- **Security Risk**: HIGH - must be unique per environment
- **How to Generate**: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

### `ALGORITHM`
- **Type**: String
- **Default**: `HS256`
- **Description**: JWT signing algorithm
- **Values**: `HS256`, `HS512`, `RS256`

### `ACCESS_TOKEN_EXPIRE_MINUTES`
- **Type**: Integer
- **Default**: `30`
- **Description**: JWT token expiration time in minutes

---

## Configuration Best Practices

### Development Environment
```bash
# Use .env.local with weak passwords for testing
POSTGRES_PASSWORD=dev_password
REDIS_PASSWORD=dev_password
ENVIRONMENT=development
LOG_LEVEL=debug
```

### Production Environment
```bash
# Use secrets manager, no .env files
# Generate secure passwords: openssl rand -base64 32
POSTGRES_PASSWORD=$(secure_random_32_chars)
REDIS_PASSWORD=$(secure_random_32_chars)
ENVIRONMENT=production
LOG_LEVEL=info
```

### Docker Compose Usage
```bash
# Load from .env file
docker-compose --env-file .env.prod up -d

# Or use docker-compose.prod.yml with environment file
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

### AWS ECS / GCP Cloud Run
- Use environment variable JSON/YAML in task definition or service configuration
- Integrate with:
  - AWS Secrets Manager / Systems Manager Parameter Store
  - GCP Secret Manager
  - HashiCorp Vault

---

## Environment Validation

### Required Variables
The application will fail to start if these are missing:
- `DATABASE_URL` or (`POSTGRES_USER` + `POSTGRES_PASSWORD` + `POSTGRES_DB`)
- LLM provider (one of: `AZURE_OPENAI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)

### Optional Variables
These have sensible defaults and are not required:
- `REDIS_PASSWORD` (defaults to no password in dev)
- `SMTP_*` (email features disabled if not set)
- `S3_*` (file storage disabled if not set)
- `SENTRY_DSN` (error tracking disabled if not set)

### Validation Script
```python
# apps/api/app/config.py example
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "pmis"
    
    environment: str = "development"
    log_level: str = "info"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

---

## Migration from Development to Production

### 1. Generate Secure Secrets
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Create Production .env File
```bash
cp .env.example .env.prod
# Edit .env.prod with production values
```

### 3. Update Critical Variables
- [ ] `POSTGRES_PASSWORD` - strong random password
- [ ] `REDIS_PASSWORD` - strong random password
- [ ] `SECRET_KEY` - generated random key
- [ ] `AZURE_OPENAI_API_KEY` / LLM key
- [ ] `NEXT_PUBLIC_API_URL` - production domain
- [ ] `CORS_ORIGINS` - production domain
- [ ] `ENVIRONMENT` - set to `production`
- [ ] `LOG_LEVEL` - set to `info`

### 4. Validate Configuration
```bash
# Check for undefined variables
grep -r 'None\|undefined' .env.prod

# Test database connection
docker-compose -f docker-compose.prod.yml exec api psql $DATABASE_URL -c "SELECT 1"
```

---

## Troubleshooting

### "connection refused" errors
- Check `DATABASE_URL` and `REDIS_URL` format
- Verify database/Redis services are running
- Check network connectivity in Docker

### "invalid API key" errors
- Verify LLM provider key is set and valid
- Check variable name matches provider (AZURE_OPENAI_API_KEY vs OPENAI_API_KEY)

### "CORS blocked" errors
- Check `NEXTPUBLIC_API_URL` is correct
- Add web domain to `CORS_ORIGINS` in API

### "permission denied" errors
- Regenerate `POSTGRES_PASSWORD` if contains special chars
- Ensure passwords don't contain `@`, `%`, or `:` (URL encoding issues)
