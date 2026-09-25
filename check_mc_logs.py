import boto3
ssm = boto3.client('ssm', region_name='us-east-1')
script = 'journalctl -u trading-agent.service --since "12 hours ago" | grep -i "MonteCarlo\|Buy Option\|Executing Speculative" | tail -n 30'
resp = ssm.send_command(
    InstanceIds=['i-0355b04fbe9b3570e'], 
    DocumentName='AWS-RunShellScript', 
    Parameters={'commands': [script]}
)
import time
time.sleep(5)
out = ssm.get_command_invocation(CommandId=resp['Command']['CommandId'], InstanceId='i-0355b04fbe9b3570e')
try:
    text = out.get('StandardOutputContent', '')
    print('OUTPUT:')
    print(text.encode('ascii', 'ignore').decode('ascii'))
except Exception as e:
    print('err:', e)
