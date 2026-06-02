# DevOps AI Platform
Live: https://ai-backend.astrodirectory.in

Features:
- AI Sentiment Analysis (5-level)
- FastAPI + PostgreSQL + Redis
- NGINX + Cloudflare SSL
- Docker Compose
- GitHub Actions CI/CD
- Automated Backups

Quick Test:
curl https://ai-backend.astrodirectory.in/health
curl -X POST https://ai-backend.astrodirectory.in/predict -H "Content-Type: application/json" -d '{"text":"I love this!"}'
