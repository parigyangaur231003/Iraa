# Deploying Iraa API to Hostinger

This guide will help you deploy your FastAPI application to Hostinger.

## Prerequisites

1. Hostinger VPS or Cloud Hosting account (shared hosting won't work for FastAPI)
2. SSH access to your server
3. Domain name (optional but recommended)

## Option 1: Deploy on Hostinger VPS (Recommended)

### Step 1: Connect to Your VPS

```bash
ssh root@your-server-ip
```

### Step 2: Install Required Software

```bash
# Update system
apt update && apt upgrade -y

# Install Python 3 and pip
apt install python3 python3-pip python3-venv -y

# Install Nginx
apt install nginx -y

# Install supervisor (to keep app running)
apt install supervisor -y
```

### Step 3: Upload Your Code

```bash
# Create application directory
mkdir -p /var/www/iraa
cd /var/www/iraa

# Upload your code (use SCP, SFTP, or Git)
# Option A: Using SCP from your local machine
# scp -r /path/to/Iraa root@your-server-ip:/var/www/iraa

# Option B: Using Git
git clone your-repository-url .
```

### Step 4: Set Up Python Environment

```bash
cd /var/www/iraa

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 5: Configure Environment Variables

```bash
# Create .env file
nano .env
```

Add your environment variables:
```
GROQ_API_KEY=your_groq_api_key
SERP_API_KEY=your_serp_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
DB_HOST=localhost
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=iraa_db
```

### Step 6: Create Supervisor Configuration

```bash
nano /etc/supervisor/conf.d/iraa.conf
```

Add this configuration:
```ini
[program:iraa]
directory=/var/www/iraa
command=/var/www/iraa/venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000
user=root
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/iraa/iraa.err.log
stdout_logfile=/var/log/iraa/iraa.out.log
```

Create log directory:
```bash
mkdir -p /var/log/iraa
```

Start the application:
```bash
supervisorctl reread
supervisorctl update
supervisorctl start iraa
```

### Step 7: Configure Nginx as Reverse Proxy

```bash
nano /etc/nginx/sites-available/iraa
```

Add this configuration:
```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or server IP

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site:
```bash
ln -s /etc/nginx/sites-available/iraa /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

### Step 8: Set Up SSL (Optional but Recommended)

```bash
# Install Certbot
apt install certbot python3-certbot-nginx -y

# Get SSL certificate
certbot --nginx -d your-domain.com
```

### Step 9: Configure Firewall

```bash
ufw allow 'Nginx Full'
ufw allow OpenSSH
ufw enable
```

## Option 2: Deploy Using Docker (Alternative)

### Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Create docker-compose.yml

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
    volumes:
      - .:/app
```

### Deploy with Docker

```bash
docker-compose up -d
```

## Accessing Your API

Once deployed, your API will be available at:
- `http://your-domain.com` or `http://your-server-ip`
- API Docs: `http://your-domain.com/docs`
- ReDoc: `http://your-domain.com/redoc`

## Management Commands

### Check application status
```bash
supervisorctl status iraa
```

### Restart application
```bash
supervisorctl restart iraa
```

### View logs
```bash
tail -f /var/log/iraa/iraa.out.log
tail -f /var/log/iraa/iraa.err.log
```

### Update application
```bash
cd /var/www/iraa
git pull  # or upload new files
source venv/bin/activate
pip install -r requirements.txt
supervisorctl restart iraa
```

## Troubleshooting

### Application won't start
```bash
# Check logs
supervisorctl tail iraa stderr
```

### Port already in use
```bash
# Find process using port 8000
lsof -i :8000
# Kill the process
kill -9 PID
```

### Database connection issues
- Ensure MySQL/PostgreSQL is installed and running
- Check database credentials in .env
- Verify database exists and user has proper permissions

## Security Best Practices

1. **Use environment variables** for all sensitive data
2. **Enable SSL/HTTPS** with Let's Encrypt
3. **Set up firewall** to only allow necessary ports
4. **Regular backups** of your database and code
5. **Keep system updated**: `apt update && apt upgrade`
6. **Use strong passwords** for all services
7. **Disable root SSH login** after setting up a regular user

## Notes

- Hostinger shared hosting doesn't support Python applications well
- VPS or Cloud hosting is required for FastAPI
- Make sure your VPS has at least 1GB RAM
- Consider using a process manager like PM2 or Supervisor
- Set up monitoring with tools like Uptime Kuma or Netdata
