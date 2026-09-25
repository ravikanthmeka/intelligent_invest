import boto3
import base64
import time

# Read files
with open('src/main.py', 'rb') as f:
    main_b64 = base64.b64encode(f.read()).decode('utf-8')
with open('src/skills/monte_carlo.py', 'rb') as f:
    mc_b64 = base64.b64encode(f.read()).decode('utf-8')

ssm = boto3.client('ssm', region_name='us-east-1')

script = f'''
python -c "
import base64

with open('/opt/intelligent_invest/src/main.py', 'wb') as f:
    f.write(base64.b64decode('{main_b64}'))

with open('/opt/intelligent_invest/src/skills/monte_carlo.py', 'wb') as f:
    f.write(base64.b64decode('{mc_b64}'))
"
chown ubuntu:ubuntu /opt/intelligent_invest/src/main.py
chown ubuntu:ubuntu /opt/intelligent_invest/src/skills/monte_carlo.py
systemctl restart trading-agent.service
'''

print('Sending command...')
resp = ssm.send_command(
    InstanceIds=['i-0355b04fbe9b3570e'], 
    DocumentName='AWS-RunShellScript', 
    Parameters={'commands': [script]}
)

time.sleep(5)
out = ssm.get_command_invocation(CommandId=resp['Command']['CommandId'], InstanceId='i-0355b04fbe9b3570e')
try:
    text = out.get('StandardOutputContent', '')
    print('OUTPUT:')
    print(text.encode('ascii', 'ignore').decode('ascii'))
except Exception as e:
    print('err:', e)
