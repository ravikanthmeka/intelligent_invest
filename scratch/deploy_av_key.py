import boto3
import os
import sys

def main():
    with open(".env", "r") as f:
        env_content = f.read()
        
    av_key = None
    for line in env_content.splitlines():
        if line.startswith("ALPHAVANTAGE_API_KEY="):
            av_key = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
            
    if not av_key:
        print("ALPHAVANTAGE_API_KEY not found in .env")
        sys.exit(1)
        
    print(f"Found Alpha Vantage Key: {av_key[:5]}...")
    
    ssm = boto3.client('ssm', region_name='us-east-1')
    commands = [
        f"echo 'ALPHAVANTAGE_API_KEY=\"{av_key}\"' >> /opt/intelligent_invest/.env",
        "cd /opt/intelligent_invest",
        "git pull origin main",
        "systemctl restart intelligent_invest_ui"
    ]
    response = ssm.send_command(
        InstanceIds=['i-0355b04fbe9b3570e'],
        DocumentName='AWS-RunShellScript',
        Parameters={'commands': commands}
    )
    print("Deployment triggered. Command ID:", response['Command']['CommandId'])

if __name__ == "__main__":
    main()
