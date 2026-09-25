import boto3
import base64
import time

with open('cover_shorts2.py', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode('utf-8')

ssm = boto3.client('ssm', region_name='us-east-1')
script = f'''
/usr/bin/python3 -c "
import base64
with open('/tmp/cover_shorts2.py', 'wb') as f:
    f.write(base64.b64decode('{b64}'))
"
export TRADING_MODE=live
export PYTHONPATH=/opt/intelligent_invest
/opt/intelligent_invest/.venv/bin/python /tmp/cover_shorts2.py
'''

print('Sending command...')
resp = ssm.send_command(
    InstanceIds=['i-0355b04fbe9b3570e'], 
    DocumentName='AWS-RunShellScript', 
    Parameters={'commands': [script]}
)

time.sleep(15)
out = ssm.get_command_invocation(CommandId=resp['Command']['CommandId'], InstanceId='i-0355b04fbe9b3570e')
try:
    text = out.get('StandardOutputContent', '')
    err = out.get('StandardErrorContent', '')
    print('OUTPUT:')
    print(text.encode('ascii', 'ignore').decode('ascii'))
    if err:
        print('ERROR:')
        print(err.encode('ascii', 'ignore').decode('ascii'))
except Exception as e:
    print('err:', e)
