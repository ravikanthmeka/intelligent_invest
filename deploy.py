import boto3
import base64
import time

# Read files
with open('src/agents/specialized.py', 'rb') as f:
    spec_b64 = base64.b64encode(f.read()).decode('utf-8')

ssm = boto3.client('ssm', region_name='us-east-1')

script = f'''
python3 -c "
import base64

with open('/opt/intelligent_invest/src/agents/specialized.py', 'wb') as f:
    f.write(base64.b64decode('{spec_b64}'))
"
chown ubuntu:ubuntu /opt/intelligent_invest/src/agents/specialized.py
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
