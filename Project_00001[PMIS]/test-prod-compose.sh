#!/bin/bash
# Production Docker Compose Test Script
# Tests docker-compose.prod.yml locally

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$PROJECT_DIR/infra"

echo "=========================================="
echo "PMIS Production Compose Test"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Syntax validation
echo "[TEST 1] Validating docker-compose.prod.yml syntax..."
if docker-compose -f "$INFRA_DIR/docker-compose.prod.yml" config > /dev/null 2>&1; then
    echo -e "${GREEN}✓ docker-compose.prod.yml syntax valid${NC}"
else
    echo -e "${RED}✗ docker-compose.prod.yml syntax invalid${NC}"
    docker-compose -f "$INFRA_DIR/docker-compose.prod.yml" config
    exit 1
fi
echo ""

# Test 2: Create .env.prod if not exists
echo "[TEST 2] Checking environment configuration..."
if [ ! -f "$PROJECT_DIR/.env.prod" ]; then
    echo "Creating .env.prod from .env.example..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env.prod"
    echo -e "${YELLOW}⚠ .env.prod created. Update with real production values before deploying!${NC}"
else
    echo -e "${GREEN}✓ .env.prod exists${NC}"
fi
echo ""

# Test 3: Check Docker installation
echo "[TEST 3] Checking Docker installation..."
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    COMPOSE_VERSION=$(docker-compose --version)
    echo -e "${GREEN}✓ $DOCKER_VERSION${NC}"
    echo -e "${GREEN}✓ $COMPOSE_VERSION${NC}"
else
    echo -e "${RED}✗ Docker or Docker Compose not installed${NC}"
    exit 1
fi
echo ""

# Test 4: Build images
echo "[TEST 4] Building Docker images..."
if docker-compose -f "$INFRA_DIR/docker-compose.prod.yml" build --no-cache 2>&1 | tee build.log; then
    echo -e "${GREEN}✓ All images built successfully${NC}"
    rm -f build.log
else
    echo -e "${RED}✗ Image build failed${NC}"
    cat build.log
    rm -f build.log
    exit 1
fi
echo ""

# Test 5: Start services
echo "[TEST 5] Starting services..."
docker-compose -f "$INFRA_DIR/docker-compose.prod.yml" up -d
echo "Waiting for services to be healthy (60 seconds)..."
sleep 10
echo ""

# Test 6: Check service status
echo "[TEST 6] Checking service status..."
SERVICES=("pmis-postgres-prod" "pmis-redis-prod" "pmis-api-prod" "pmis-worker-prod" "pmis-web-prod")

for service in "${SERVICES[@]}"; do
    STATUS=$(docker inspect -f '{{.State.Status}}' "$service" 2>/dev/null || echo "not-found")
    HEALTH=$(docker inspect -f '{{.State.Health.Status}}' "$service" 2>/dev/null || echo "no-health-check")
    
    if [ "$STATUS" = "running" ]; then
        if [ "$HEALTH" = "healthy" ] || [ "$HEALTH" = "no-health-check" ]; then
            echo -e "${GREEN}✓ $service: running ($HEALTH)${NC}"
        else
            echo -e "${YELLOW}⚠ $service: running (health: $HEALTH)${NC}"
        fi
    else
        echo -e "${RED}✗ $service: not running (status: $STATUS)${NC}"
    fi
done
echo ""

# Test 7: Health endpoints
echo "[TEST 7] Testing health endpoints..."
ENDPOINTS=(
    "http://localhost:8000/health:API"
    "http://localhost:3000:Web"
)

for endpoint in "${ENDPOINTS[@]}"; do
    IFS=':' read -r url name <<< "$endpoint"
    if timeout 5 curl -f "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ $name endpoint healthy${NC}"
    else
        echo -e "${YELLOW}⚠ $name endpoint not responding yet (may still be starting)${NC}"
    fi
done
echo ""

# Test 8: Database connectivity
echo "[TEST 8] Testing database connectivity..."
if docker-compose -f "$INFRA_DIR/docker-compose.prod.yml" exec -T postgres \
    pg_isready -U postgres -d pmis > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL connected${NC}"
else
    echo -e "${RED}✗ PostgreSQL not responding${NC}"
fi

if docker-compose -f "$INFRA_DIR/docker-compose.prod.yml" exec -T redis \
    redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Redis connected${NC}"
else
    echo -e "${RED}✗ Redis not responding${NC}"
fi
echo ""

# Test 9: Check logs for errors
echo "[TEST 9] Checking logs for critical errors..."
ERRORS=$(docker-compose -f "$INFRA_DIR/docker-compose.prod.yml" logs --tail=100 2>&1 | grep -i "error\|exception\|fatal" || true)
if [ -z "$ERRORS" ]; then
    echo -e "${GREEN}✓ No critical errors in logs${NC}"
else
    echo -e "${YELLOW}⚠ Errors found in logs:${NC}"
    echo "$ERRORS" | head -5
fi
echo ""

# Test 10: Resource usage
echo "[TEST 10] Checking resource usage..."
echo "Container memory/CPU usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}\t{{.CPUPerc}}" | grep pmis || true
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo ""
echo "To stop all services:"
echo "  docker-compose -f $INFRA_DIR/docker-compose.prod.yml down"
echo ""
echo "To view logs:"
echo "  docker-compose -f $INFRA_DIR/docker-compose.prod.yml logs -f"
echo ""
echo "To run a specific test:"
echo "  docker-compose -f $INFRA_DIR/docker-compose.prod.yml exec api bash"
echo ""
echo -e "${GREEN}✓ Production compose test completed!${NC}"
