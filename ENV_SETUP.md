# Environment Variables Setup Guide

## Step 1: Add GitHub Secret

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `ENV_FILE`
5. Value: Copy and paste the content below (update with your actual values):

```
SECRET_KEY=spotpay-prod-CHANGE-ME-TO-A-LONG-RANDOM-STRING
DEBUG=False
DATABASE_URL=postgresql://postgres:Vicojohn%40100@db.taaqmbagazeduvdavrsg.supabase.co:5432/postgres?sslmode=require
ALLOWED_HOSTS=69.164.245.17,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://69.164.245.17:8001,http://69.164.245.17,http://127.0.0.1:8000,http://localhost:8000
SITE_URL=http://69.164.245.17:8001
PORTAL_API_BASE=http://69.164.245.17:8001/api/portal
```

## Step 2: Verify Existing Secrets

Make sure these secrets are already configured:
- `VPS_HOST` - Your VPS IP (69.164.245.17)
- `VPS_USER` - SSH username (root)
- `VPS_SSH_KEY` - Your private SSH key
- `VPS_PORT` - SSH port (usually 22)

## Step 3: Update VPS Manually (One-time)

SSH into your VPS and create the .env file:

```bash
ssh root@69.164.245.17
cd /root/SpotPay-deployment
nano .env
```

Paste your environment variables, save (Ctrl+X, Y, Enter), then restart:

```bash
docker compose down
docker compose up -d --build
```

## Step 4: Test Deployment

Push to main branch - GitHub Actions will now automatically update the .env file on each deployment.

## Security Notes

- ✅ `.env` is in `.gitignore` (never commit it)
- ✅ Use GitHub Secrets for sensitive data
- ⚠️ Generate a strong SECRET_KEY for production
- ⚠️ Consider using HTTPS in production
