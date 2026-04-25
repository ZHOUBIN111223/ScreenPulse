# ScreenPulse Server Deployment

This repository is prepared for deployment on `47.104.158.30`.

## First Deploy

Run these commands on the server:

```bash
git clone https://github.com/ZHOUBIN111223/ScreenPulse.git
cd ScreenPulse
sh scripts/init-server-env.sh
docker compose up -d --build
```

The init script creates `.env` only when it does not already exist. It writes:

- `NEXT_PUBLIC_API_BASE_URL=http://47.104.158.30:8011/api`
- `SCREENPULSE_CORS_ORIGINS=http://47.104.158.30:3001`
- a generated `SCREENPULSE_SECRET_KEY`

## Ports

Open these ports in the server firewall and cloud security group:

- `3001`: frontend
- `8011`: backend API

## Local Development

Local settings stay in the ignored `.env` file and can keep using `localhost`.
Those values are not committed.

## Docker Mirrors

Docker builds use Aliyun-hosted base images. Backend Python packages use the
Aliyun PyPI mirror, and frontend npm packages use the npmmirror registry.
