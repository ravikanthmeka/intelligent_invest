import boto3
import time

ssm = boto3.client('ssm', region_name='us-east-1')

commands = [
    "cat /opt/intelligent_invest/data/considerations.json | tail -n 100"
]

response = ssm.send_command(
    InstanceIds=['i-0355b04fbe9b3570e'],
    DocumentName='AWS-RunShellScript',
    Parameters={'commands': commands}
)

command_id = response['Command']['CommandId']

time.sleep(5)
try:
    output = ssm.get_command_invocation(
        CommandId=command_id,
        InstanceId='i-0355b04fbe9b3570e'
    )
    print("Output:\n", output['StandardOutputContent'])
except Exception as e:
    pass
