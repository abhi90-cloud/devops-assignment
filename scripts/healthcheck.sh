#!/bin/bash

echo "=== DevOps App Health Check ==="
echo "Timestamp: $(date)"
echo ""

# Check Docker services
echo "Docker Services:"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(fastapi|postgres|redis|nginx)"

echo ""
echo "Application Health:"
curl -s http://localhost/health | python3 -m json.tool 2>/dev/null || echo "Failed to get health status"

echo ""
echo "System Resources:"
echo "CPU Usage: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')%"
echo "Memory Usage: $(free -m | awk 'NR==2{printf "%.2f%%", $3*100/$2}')"
echo "Disk Usage: $(df -h / | awk 'NR==2{print $5}')"
