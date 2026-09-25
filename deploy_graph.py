import boto3
import base64
import time

def encode_file(path):
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

b64_spec = encode_file('src/agents/specialized.py')
b64_init = encode_file('src/graph_rag/__init__.py')
b64_tool = encode_file('src/graph_rag/graph_tool.py')
b64_graph = encode_file('src/graph_rag/temporal_graph.py')
b64_ingest = encode_file('src/graph_rag/ingestion_pipeline.py')
b64_docker = encode_file('docker-compose.neo4j.yaml')
b64_reqs = encode_file('requirements.txt')

ssm = boto3.client('ssm', region_name='us-east-1')

script = f'''
mkdir -p /opt/intelligent_invest/src/graph_rag

/usr/bin/python3 -c "
import base64
with open('/opt/intelligent_invest/src/agents/specialized.py', 'wb') as f:
    f.write(base64.b64decode('{b64_spec}'))
with open('/opt/intelligent_invest/src/graph_rag/__init__.py', 'wb') as f:
    f.write(base64.b64decode('{b64_init}'))
with open('/opt/intelligent_invest/src/graph_rag/graph_tool.py', 'wb') as f:
    f.write(base64.b64decode('{b64_tool}'))
with open('/opt/intelligent_invest/src/graph_rag/temporal_graph.py', 'wb') as f:
    f.write(base64.b64decode('{b64_graph}'))
with open('/opt/intelligent_invest/src/graph_rag/ingestion_pipeline.py', 'wb') as f:
    f.write(base64.b64decode('{b64_ingest}'))
with open('/opt/intelligent_invest/docker-compose.neo4j.yaml', 'wb') as f:
    f.write(base64.b64decode('{b64_docker}'))
with open('/opt/intelligent_invest/requirements.txt', 'wb') as f:
    f.write(base64.b64decode('{b64_reqs}'))
"

chown -R ubuntu:ubuntu /opt/intelligent_invest/src/graph_rag

cd /opt/intelligent_invest
/opt/intelligent_invest/.venv/bin/pip install neo4j yfinance

# Start neo4j container
docker-compose -f docker-compose.neo4j.yaml up -d

# Restart trading agent service
systemctl restart trading-agent.service
'''

print('Sending command to EC2 instance...')
resp = ssm.send_command(
    InstanceIds=['i-0355b04fbe9b3570e'], 
    DocumentName='AWS-RunShellScript', 
    Parameters={'commands': [script]}
)

print('Command sent, waiting for execution...')
time.sleep(15)

out = ssm.get_command_invocation(CommandId=resp['Command']['CommandId'], InstanceId='i-0355b04fbe9b3570e')
try:
    text = out.get('StandardOutputContent', '')
    err = out.get('StandardErrorContent', '')
    print('OUTPUT:')
    print(text)
    if err:
        print('ERROR:')
        print(err)
except Exception as e:
    print('err:', e)
