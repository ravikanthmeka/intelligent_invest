import boto3
import time

ssm = boto3.client('ssm', region_name='us-east-1')
script = 'journalctl -u trading-agent.service -n 50'

resp = ssm.send_command(
    InstanceIds=['i-0355b04fbe9b3570e'], 
    DocumentName='AWS-RunShellScript', 
    Parameters={'commands': [script]}
)

time.sleep(5)
out = ssm.get_command_invocation(CommandId=resp['Command']['CommandId'], InstanceId='i-0355b04fbe9b3570e')
print('OUTPUT:')
print(out.get('StandardOutputContent', ''))
