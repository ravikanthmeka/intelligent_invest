import subprocess
import os
import yaml

# 1. Update .env to live mode
env_path = "/opt/intelligent_invest/.env"
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        if line.startswith("IBKR_TRADING_MODE="):
            new_lines.append('IBKR_TRADING_MODE="live"\n')
        else:
            new_lines.append(line)
            
    with open(env_path, "w") as f:
        f.writelines(new_lines)
    print("Updated .env to live mode.")

# 2. Update config.yaml to live port 4001
config_path = "/opt/intelligent_invest/config.yaml"
if os.path.exists(config_path):
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
        
    if "broker" not in cfg:
        cfg["broker"] = {}
    cfg["broker"]["port"] = 4001
    
    if "trading" not in cfg:
        cfg["trading"] = {}
    cfg["trading"]["dry_run"] = False
    
    with open(config_path, "w") as f:
        yaml.safe_dump(cfg, f)
    print("Updated config.yaml to port 4001 and dry_run: false.")

# 3. Restart docker-compose
os.chdir("/opt/intelligent_invest")
subprocess.run(["docker", "compose", "-f", "docker-compose.ib.yaml", "down"], check=False)
subprocess.run(["docker", "compose", "-f", "docker-compose.ib.yaml", "up", "-d"], check=True)
print("IB Gateway container restarted in Live Mode.")
