# Deployment Guide
Production URL: https://ai-backend.astrodirectory.in

Quick Deploy:
  git clone https://github.com/YOUR_USER/devops-assignment.git
  cp .env.example .env
  docker compose up -d --build

API:
  GET /health - Health check
  POST /predict - Predict sentiment
  GET /predictions - History
  GET /analytics - Analytics
  GET /docs - Swagger docs
