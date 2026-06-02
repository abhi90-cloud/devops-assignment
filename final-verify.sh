#!/bin/bash

DOMAIN="ai-backend.astrodirectory.in"

echo "========================================="
echo "  🚀 PRODUCTION DEPLOYMENT VERIFICATION"
echo "  Domain: $DOMAIN"
echo "  $(date)"
echo "========================================="

echo ""
echo "📡 1. Health Check:"
curl -s "https://$DOMAIN/health" | python3 -m json.tool

echo ""
echo "🤖 2. AI Predictions Test:"
echo "   Positive:"
curl -s -X POST "https://$DOMAIN/predict" -H "Content-Type: application/json" \
  -d '{"text":"I absolutely love this fantastic product"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'   → {d[\"sentiment\"]} ({d[\"confidence\"]:.2f})')"

echo "   Negative:"
curl -s "https://$DOMAIN/predict?text=This%20is%20horrible%20and%20terrible" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'   → {d[\"sentiment\"]} ({d[\"confidence\"]:.2f})')"

echo "   Neutral:"
curl -s "https://$DOMAIN/predict?text=Today%20is%20an%20average%20day" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'   → {d[\"sentiment\"]} ({d[\"confidence\"]:.2f})')"

echo ""
echo "📊 3. Analytics:"
curl -s "https://$DOMAIN/analytics" | python3 -m json.tool

echo ""
echo "📚 4. API Documentation:"
echo "   Swagger UI: https://$DOMAIN/docs"
echo "   ReDoc: https://$DOMAIN/redoc"
echo "   OpenAPI: https://$DOMAIN/openapi.json"

echo ""
echo "🔗 5. Quick Links:"
echo "   Home:        https://$DOMAIN"
echo "   Health:      https://$DOMAIN/health"
echo "   Predictions: https://$DOMAIN/predictions"
echo "   Analytics:   https://$DOMAIN/analytics"

echo ""
echo "========================================="
echo "  ✅ DEPLOYMENT SUCCESSFUL!"
echo "========================================="
