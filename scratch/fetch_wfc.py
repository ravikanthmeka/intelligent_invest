import boto3
import time
ssm = boto3.client('ssm', region_name='us-east-1')
commands = ['jq \'.completed_trades | map(select(.symbol == "WFC"))\' /opt/intelligent_invest/trading_state.json']
resp = ssm.send_command(InstanceIds=['i-0355b04fbe9b3570e'], DocumentName='AWS-RunShellScript', Parameters={'commands': commands})
time.sleep(4)
out = ssm.get_command_invocation(CommandId=resp['Command']['CommandId'], InstanceId='i-0355b04fbe9b3570e')
print(out['StandardOutputContent'])
