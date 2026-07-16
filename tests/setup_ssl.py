import subprocess
import os

# 1. Create SSL directory
os.makedirs("/opt/intelligent_invest/ssl", exist_ok=True)

# 2. Generate self-signed certificate
cmd_cert = [
    "openssl", "req", "-x509", "-nodes", "-days", "365", "-newkey", "rsa:2048",
    "-keyout", "/opt/intelligent_invest/ssl/key.pem",
    "-out", "/opt/intelligent_invest/ssl/cert.pem",
    "-subj", "/C=US/ST=NewYork/L=NewYork/O=IntelligentInvest/OU=IT/CN=44.223.87.185"
]
subprocess.run(cmd_cert, check=True)
print("Generated SSL certificate successfully.")

# 3. Write systemd service file
service_content = """[Unit]
Description=Intelligent Invest Trading Dashboard Web UI
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/intelligent_invest
ExecStart=/opt/intelligent_invest/.venv/bin/streamlit run /opt/intelligent_invest/src/dashboard.py --server.port 8501 --server.address 0.0.0.0 --server.sslCertFile /opt/intelligent_invest/ssl/cert.pem --server.sslKeyFile /opt/intelligent_invest/ssl/key.pem
Restart=always
User=root
"""

with open("/etc/systemd/system/trading-dashboard.service", "w") as f:
    f.write(service_content)
print("Updated systemd service file successfully.")

# 4. Reload and restart service
subprocess.run(["systemctl", "daemon-reload"], check=True)
subprocess.run(["systemctl", "restart", "trading-dashboard.service"], check=True)
print("Streamlit dashboard restarted with SSL enabled.")
