import boto3
import time

ssm = boto3.client('ssm', region_name='us-east-1')

commands = [
    "ls -l /etc/systemd/system/ | grep intelligent",
    "cat /var/log/streamlit.log || true"
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
    print("Status:", output['Status'])
    print("Output:\n", output['StandardOutputContent'])
    print("Error:\n", output['StandardErrorContent'])
except Exception as e:
    print(f"Could not fetch output immediately: {e}")
