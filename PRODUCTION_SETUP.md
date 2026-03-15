# Production Setup Guide for spotpay.it.com

## Prerequisites
- Domain `spotpay.it.com` DNS configured to point to your VPS IP
- VPS with Docker and Docker Compose installed
- GitHub repository secrets configured

## Step 1: DNS Configuration

Configure your DNS records for `spotpay.it.com`:

```
Type    Name    Value           TTL
A       @       YOUR_VPS_IP     3600
A       www     YOUR_VPS_IP     3600
```

Wait for DNS propagation (can take up to 48 hours, usually 5-30 minutes).

## Step 2: Update GitHub Secrets

Update your `ENV_FILE` secret in GitHub repository settings to include:

```env
# Django Settings
SECRET_KEY=your-production-secret-key-here
DEBUG=False

# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require

# Allowed Hosts & CSRF
ALLOWED_HOSTS=spotpay.it.com,www.spotpay.it.com,YOUR_VPS_IP,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://spotpay.it.com,https://www.spotpay.it.com,http://YOUR_VPS_IP:8001

# Site Configuration
SITE_URL=https://spotpay.it.com
PORTAL_API_BASE=https://spotpay.it.com/api/portal

# CORS Configuration
CORS_ALLOWED_ORIGINS=https://spotpay.it.com,https://www.spotpay.it.com
CORS_ALLOW_ALL_ORIGINS=True
```

## Step 3: SSL Certificate Setup (Let's Encrypt)

SSH into your VPS and run:

```bash
# Install certbot
sudo apt update
sudo apt install certbot python3-certbot-nginx -y

# Stop nginx temporarily
cd /root/SpotPay-deployment
docker compose stop nginx

# Obtain SSL certificate
sudo certbot certonly --standalone -d spotpay.it.com -d www.spotpay.it.com

# Certificate will be saved to:
# /etc/letsencrypt/live/spotpay.it.com/fullchain.pem
# /etc/letsencrypt/live/spotpay.it.com/privkey.pem
```

## Step 4: Enable HTTPS in nginx.conf

After obtaining SSL certificate, uncomment the HTTPS server block in `nginx.conf`:

1. Comment out or remove the HTTP redirect line in the HTTP server block
2. Uncomment the entire HTTPS server block (lines starting with `# server {`)
3. Verify SSL certificate paths match your certbot installation

## Step 5: Update docker-compose.yml for SSL

Add SSL certificate volumes to nginx service in `docker-compose.yml`:

```yaml
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
    - "443:443"  # Add HTTPS port
  volumes:
    - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    - ./staticfiles:/app/staticfiles:ro
    - ./media:/app/media:ro
    - /etc/letsencrypt:/etc/letsencrypt:ro  # Add SSL certificates
  depends_on:
    - web
  restart: unless-stopped
```

## Step 6: Deploy via GitHub Actions

Push your changes to trigger automatic deployment:

```bash
git add -A
git commit -m "feat: add production domain support for spotpay.it.com"
git push origin main
```

GitHub Actions will automatically:
- Pull latest code on VPS
- Create `.env` file with production settings
- Build Docker containers
- Run migrations and collect static files
- Deploy with zero downtime

## Step 7: Verify Deployment

1. Check HTTP access: `http://spotpay.it.com`
2. Check HTTPS access: `https://spotpay.it.com`
3. Verify CORS headers in browser DevTools
4. Test captive portal functionality

## Step 8: SSL Certificate Auto-Renewal

Set up automatic SSL certificate renewal:

```bash
# Test renewal
sudo certbot renew --dry-run

# Add cron job for auto-renewal
sudo crontab -e

# Add this line to renew certificates twice daily
0 0,12 * * * certbot renew --quiet --post-hook "cd /root/SpotPay-deployment && docker compose restart nginx"
```

## Troubleshooting

### DNS not resolving
```bash
# Check DNS propagation
nslookup spotpay.it.com
dig spotpay.it.com
```

### SSL certificate issues
```bash
# Check certificate validity
sudo certbot certificates

# Renew manually
sudo certbot renew --force-renewal
```

### CORS errors
- Verify `CORS_ALLOWED_ORIGINS` includes your domain
- Check browser console for specific CORS errors
- Ensure `CORS_ALLOW_ALL_ORIGINS=True` for captive portals

### Container logs
```bash
cd /root/SpotPay-deployment
docker compose logs -f web
docker compose logs -f nginx
```

## Security Checklist

- [ ] `DEBUG=False` in production
- [ ] Strong `SECRET_KEY` generated
- [ ] Database uses SSL connection
- [ ] HTTPS enabled with valid SSL certificate
- [ ] `ALLOWED_HOSTS` properly configured
- [ ] `CSRF_TRUSTED_ORIGINS` includes production domain
- [ ] Firewall configured (ports 80, 443, 22 only)
- [ ] Regular database backups configured
- [ ] SSL certificate auto-renewal enabled

## Maintenance

### Update application
```bash
# Push to GitHub - automatic deployment via Actions
git push origin main
```

### Manual deployment (if needed)
```bash
ssh user@YOUR_VPS_IP
cd /root/SpotPay-deployment
git pull origin main
docker compose build
docker compose up -d
```

### Database backup
```bash
# Backup database
docker compose exec db pg_dump -U postgres dbname > backup_$(date +%Y%m%d).sql

# Restore database
docker compose exec -T db psql -U postgres dbname < backup_20250101.sql
```

## Support

For issues or questions:
- Email: support@spotpay.it.com
- Check logs: `docker compose logs -f`
- Review GitHub Actions deployment logs

## Captive Portal ZIP Generation

The system generates customized captive portal files for each location:

### How it works:
1. Admin uploads a base portal template ZIP via Django admin (`PortalTemplate` model)
2. Template contains HTML/CSS/JS files with placeholders:
   - `{{API_BASE}}` - Replaced with your API endpoint
   - `{{LOCATION_UUID}}` - Replaced with location's unique ID
   - `{{SUPPORT_PHONE}}` - Replaced with vendor's support phone
3. Vendor downloads customized ZIP from: `/api/portal-download/<location-uuid>/`
4. System dynamically replaces placeholders and generates location-specific portal

### Portal Template Structure:
```
portal-template.zip
├── index.html          (with {{API_BASE}}, {{LOCATION_UUID}} placeholders)
├── portal.js           (API calls to {{API_BASE}}/portal/{{LOCATION_UUID}}/)
├── styles.css
└── assets/
    ├── logo.png
    └── background.jpg
```

### Upload Portal Template:
1. Go to Django Admin: `/admin/portal_api/portaltemplate/`
2. Upload ZIP file with portal template
3. Mark as active
4. Vendors can now download customized portals for their locations
