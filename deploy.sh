#!/bin/bash
# Run on Vultr VM
set -e

echo "🚀 Deploying MediFlow..."

# Update code
git pull origin main

# Cleanup temp files before rebuild
sudo rm -rf /tmp/mediflow/* || true

# Rebuild and restart stack
docker-compose down
docker-compose build --no-cache
docker-compose up -d

echo "⏳ Waiting for health check..."
MAX_RETRIES=5
COUNT=0

while [ $COUNT -lt $MAX_RETRIES ]; do
  if curl -f http://localhost/api/health > /dev/null 2>&1; then
    echo "✅ Deploy success!"
    exit 0
  fi
  echo "Retrying health check ($((COUNT+1))/$MAX_RETRIES)..."
  sleep 10
  COUNT=$((COUNT+1))
done

echo "❌ Health check failed after $MAX_RETRIES attempts"
docker-compose logs backend
exit 1
