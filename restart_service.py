import boto3
import time

ssm = boto3.client('ssm', region_name='us-east-1')
script = '''
sudo systemctl restart trading-agent.service
'''

print('Restarting service...')
resp = ssm.send_command(
    InstanceIds=['i-0355b04fbe9b3570e'], 
    DocumentName='AWS-RunShellScript', 
    Parameters={'commands': [script]}
)

time.sleep(5)
out = ssm.get_command_invocation(CommandId=resp['Command']['CommandId'], InstanceId='i-0355b04fbe9b3570e')
try:
    print('OUTPUT:', out.get('StandardOutputContent', ''))
    err = out.get('StandardErrorContent', '')
    if err:
        print('ERROR:', err)
except Exception as e:
    print('err:', e)
