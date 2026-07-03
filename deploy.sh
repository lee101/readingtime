#!/bin/bash
# Deploy script for readingtime.app.nz
set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
cd /nvme0n1-disk/code/readingtime

echo -e "${YELLOW}Building...${NC}"
go build -o readingtime .
echo -e "${GREEN}Built${NC}"

# Install/refresh the systemd unit.
if ! cmp -s systemd/readingtime.service /etc/systemd/system/readingtime.service 2>/dev/null; then
    echo -e "${YELLOW}Installing systemd unit...${NC}"
    sudo cp systemd/readingtime.service /etc/systemd/system/readingtime.service
    sudo systemctl daemon-reload
    sudo systemctl enable readingtime.service
fi

# Install/refresh the nginx vhost (exact server_name beats the *.app.nz wildcard).
if ! cmp -s nginx/readingtime.app.nz /etc/nginx/sites-available/readingtime.app.nz 2>/dev/null; then
    echo -e "${YELLOW}Installing nginx vhost...${NC}"
    sudo cp nginx/readingtime.app.nz /etc/nginx/sites-available/readingtime.app.nz
    sudo ln -sf /etc/nginx/sites-available/readingtime.app.nz /etc/nginx/sites-enabled/readingtime.app.nz
    sudo nginx -t && sudo systemctl reload nginx
fi

echo -e "${YELLOW}Restarting readingtime.service...${NC}"
sudo systemctl restart readingtime.service
sleep 2
if systemctl is-active --quiet readingtime.service; then
    echo -e "${GREEN}readingtime.service running${NC}"
else
    echo -e "${RED}readingtime.service failed${NC}"
    journalctl -u readingtime.service --no-pager -n 20
    exit 1
fi

for i in $(seq 1 20); do
    if curl -sf http://127.0.0.1:4337/health >/dev/null 2>&1; then
        echo -e "${GREEN}Health OK — https://readingtime.app.nz${NC}"; break
    fi
    [ "$i" -eq 20 ] && { echo -e "${RED}Not healthy${NC}"; exit 1; }
    sleep 1
done
