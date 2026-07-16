#!/bin/bash
docker exec -u 0 ib-gateway apt-get update
docker exec -u 0 ib-gateway apt-get install -y scrot
docker exec ib-gateway sh -c "DISPLAY=:1 scrot -z /tmp/screenshot.png"
docker cp ib-gateway:/tmp/screenshot.png /opt/intelligent_invest/screenshot.png
python3 -c "import base64; open('/opt/intelligent_invest/screenshot.txt', 'w').write(base64.b64encode(open('/opt/intelligent_invest/screenshot.png', 'rb').read()).decode('utf-8'))"
echo "Screenshot captured and base64 encoded successfully!"
