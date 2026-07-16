#!/bin/bash
set -e

# Redirect logs
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "================ Starting Bootstrapping ================"

# 1. Update and install dependencies
yum update -y
yum install -y docker git python3-pip python3-devel

# Start Docker
systemctl enable docker
systemctl start docker

# Add ssm agent (usually pre-installed on Amazon Linux 2023, but make sure it is running)
systemctl enable amazon-ssm-agent
systemctl start amazon-ssm-agent

# Install Docker Compose (v2)
mkdir -p /usr/local/lib/docker/cli-plugins/
curl -SL https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# 2. Clone Repository
REPO_URL="${repo_url}"
APP_DIR="/opt/intelligent_invest"

echo "Cloning repository $REPO_URL to $APP_DIR..."
git clone "$REPO_URL" "$APP_DIR"
cd "$APP_DIR"

# 3. Resolve Environment Variables from SSM Parameter Store
# (If parameters don't exist yet, it will create empty values in .env)
echo "Resolving credentials from SSM Parameter Store..."
aws_region="${aws_region}"

get_ssm_param() {
  local param_name=$1
  aws ssm get-parameter --name "$param_name" --with-decryption --region "$aws_region" --query "Parameter.Value" --output text 2>/dev/null || echo ""
}

ibkr_user=$(get_ssm_param "/trading/ibkr_userid")
ibkr_pass=$(get_ssm_param "/trading/ibkr_password")
telegram_token=$(get_ssm_param "/trading/telegram_bot_token")
telegram_users=$(get_ssm_param "/trading/telegram_allowed_users")

# Write .env file
cat <<EOF > .env
# Auto-generated .env from userdata
AWS_REGION="$aws_region"
IBKR_USERID="$ibkr_user"
IBKR_PASSWORD="$ibkr_pass"
IBKR_TRADING_MODE="paper"

# Telegram settings (if needed in the future)
TELEGRAM_BOT_TOKEN="$telegram_token"
TELEGRAM_ALLOWED_USERS="$telegram_users"
EOF

# 4. Set up Virtual Environment and Dependencies
echo "Setting up Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Launch IB Gateway in Docker
echo "Starting IB Gateway container..."
docker compose -f docker-compose.ib.yaml up -d

# 6. Create Systemd Service and Timer for Trading Cycle
echo "Setting up Systemd Timer for trading cycle..."

# Service definition
cat <<EOF > /etc/systemd/system/trading-agent.service
[Unit]
Description=Intelligent Invest Multi-Agent Trading Cycle
After=network.target

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/src/main.py
Environment=PYTHONPATH=$APP_DIR
User=root
EOF

# Timer definition (Runs every hour during trading hours on weekdays)
cat <<EOF > /etc/systemd/system/trading-agent.timer
[Unit]
Description=Run Intelligent Invest Trading Cycle every hour during trading hours

[Timer]
OnCalendar=Mon-Fri *-*-* 09,10,11,12,13,14,15:30:00
Unit=trading-agent.service

[Install]
WantedBy=timers.target
EOF

# Dashboard service definition
cat <<EOF > /etc/systemd/system/trading-dashboard.service
[Unit]
Description=Intelligent Invest Trading Dashboard Web UI
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/streamlit run $APP_DIR/src/dashboard.py --server.port 8501 --server.address 0.0.0.0
Restart=always
User=root
EOF

# Reload and enable services
systemctl daemon-reload
systemctl enable trading-agent.timer
systemctl start trading-agent.timer
systemctl enable trading-dashboard.service
systemctl start trading-dashboard.service

echo "================ Bootstrapping Complete ================"
