import boto3
import time

ssm = boto3.client('ssm', region_name='us-east-1')

# List the recent command invocations for the instance
resp = ssm.list_command_invocations(
    InstanceId='i-0355b04fbe9b3570e',
    MaxResults=3,
    Details=True
)

for inv in resp['CommandInvocations']:
    print(f"CommandId: {inv['CommandId']}, Status: {inv['Status']}")
    if 'CommandPlugins' in inv and len(inv['CommandPlugins']) > 0:
        plugin = inv['CommandPlugins'][0]
        print(f"OUTPUT:\n{plugin.get('Output', '')}")
        print(f"ERROR_CONTENT:\n{plugin.get('StandardErrorContent', '')}")
    print("-" * 40)
