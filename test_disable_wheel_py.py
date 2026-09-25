import boto3
import time
ssm = boto3.client('ssm', region_name='us-east-1')
script = '''
python -c "
with open('/opt/intelligent_invest/src/main.py', 'r') as f:
    c = f.read()
c = c.replace('watchlist = config.get(\\'watchlist\\', [])', 'watchlist = [] # Temporarily disable Wheel strategy per user request (was config.get(\\'watchlist\\', []))')
with open('/opt/intelligent_invest/src/main.py', 'w') as f:
    f.write(c)
"
systemctl restart trading-agent.service
'''
resp = ssm.send_command(InstanceIds=['i-0355b04fbe9b3570e'], DocumentName='AWS-RunShellScript', Parameters={'commands': [script]})
time.sleep(5)
out = ssm.get_command_invocation(CommandId=resp['Command']['CommandId'], InstanceId='i-0355b04fbe9b3570e')
try:
    text = out.get('StandardOutputContent', '')
    print('OUTPUT:')
    print(text.encode('ascii', 'ignore').decode('ascii'))
except Exception as e:
    print('err:', e)
