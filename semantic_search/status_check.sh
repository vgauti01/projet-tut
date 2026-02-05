#!/bin/bash

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 Semantic Search - Status Dashboard"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check services
echo "📦 Services Status:"
docker compose ps --format "table {{.Service}}\t{{.Status}}" | grep -E "Service|api|frontend|prometheus|grafana|meilisearch|qdrant"
echo ""

# Check API health
echo "💚 API Health:"
health=$(curl -s http://localhost:8000/health/deep | jq -r '.status' 2>/dev/null)
if [ "$health" = "healthy" ]; then
  echo "  ✅ Status: HEALTHY"
else
  echo "  ⚠️  Status: $health"
fi

models=$(curl -s http://localhost:8000/health/deep | jq -r '.models.embed_model' 2>/dev/null)
echo "  🧠 Models: $models"
echo ""

# Check metrics
echo "📊 Metrics Summary:"
requests=$(curl -s http://localhost:8000/metrics | grep "^search_requests_total" | awk '{sum+=$2} END {print sum}')
echo "  📈 Total searches: ${requests:-0}"

meili_latency=$(curl -s http://localhost:8000/metrics | grep 'search_duration_seconds_sum{stage="meili"}' | awk '{print $2}')
qdrant_latency=$(curl -s http://localhost:8000/metrics | grep 'search_duration_seconds_sum{stage="qdrant"}' | awk '{print $2}')
echo "  ⏱️  Meili total time: ${meili_latency:-0}s"
echo "  ⏱️  Qdrant total time: ${qdrant_latency:-0}s"
echo ""

# Check Prometheus
echo "🔍 Prometheus Status:"
api_target=$(curl -s http://localhost:9090/api/v1/targets 2>/dev/null | jq -r '.data.activeTargets[] | select(.labels.job=="api") | .health')
if [ "$api_target" = "up" ]; then
  echo "  ✅ Scraping API: UP"
else
  echo "  ❌ Scraping API: DOWN"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Access URLs:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  🔹 API:            http://localhost:8000"
echo "  🔹 API Health:     http://localhost:8000/health/deep"
echo "  🔹 API Metrics:    http://localhost:8000/metrics"
echo "  🔹 Frontend:       http://localhost:5173"
echo "  🔹 Prometheus:     http://localhost:9090"
echo "  🔹 Grafana:        http://localhost:3000 (admin/admin)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 Quick Actions:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Generate traffic:"
echo "    for i in {1..10}; do curl -s -X POST http://localhost:8000/ask -H 'Content-Type: application/json' -d '{\"query\": \"test\"}' > /dev/null && echo \"✓ \$i\"; done"
echo ""
echo "  Test degraded mode:"
echo "    docker compose stop meilisearch"
echo "    # Make some requests, then:"
echo "    docker compose start meilisearch"
echo ""
echo "  View logs:"
echo "    docker compose logs -f api"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
