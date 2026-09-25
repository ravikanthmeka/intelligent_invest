import boto3
import time
ssm = boto3.client('ssm', region_name='us-east-1')
script = '''
sqlite3 /opt/intelligent_invest/trading_state.db "SELECT ticker, strike, option_type, action, status, filled FROM portfolio_options;"
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
