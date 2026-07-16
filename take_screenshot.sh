#!/bin/bash
docker exec -u 0 ib-gateway apt-get update
docker exec -u 0 ib-gateway apt-get install -y scrot
docker exec ib-gateway sh -c "DISPLAY=:1 scrot -z /tmp/screenshot.png"
docker cp ib-gateway:/tmp/screenshot.png /opt/intelligent_invest/screenshot.png
echo "Screenshot captured successfully!"
