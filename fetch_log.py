import boto3
import time

ssm = boto3.client('ssm', region_name='us-east-1')
script = 'tail -n 1000 /opt/intelligent_invest/trading_system.log'

resp = ssm.send_command(
    InstanceIds=['i-0355b04fbe9b3570e'], 
    DocumentName='AWS-RunShellScript', 
    Parameters={'commands': [script]}
)

time.sleep(5)
out = ssm.get_command_invocation(CommandId=resp['Command']['CommandId'], InstanceId='i-0355b04fbe9b3570e')
content = out.get('StandardOutputContent', '').strip()

if content:
    with open('trading_system.log', 'w') as f:
        f.write(content)
    print("trading_system.log updated locally.")
else:
    print("Failed to fetch log content:", out.get('StandardErrorContent'))
