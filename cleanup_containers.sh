#!/bin/bash
echo "Stopping containers on port 80..."
# Find container ID mapped to port 80
CID=$(docker ps -q --filter publish=80)
if [ ! -z "$CID" ]; then
    docker stop $CID
    docker rm $CID
    echo "Container $CID removed."
else
    echo "No container found on port 80."
fi

echo "Restarting Nginx..."
systemctl restart nginx
status=$?
if [ $status -ne 0 ]; then
    echo "Nginx failed to restart."
    journalctl -xeu nginx.service | tail -n 20
    exit 1
fi

echo "Checking API..."
curl -I http://localhost/api/ask/llm-status
