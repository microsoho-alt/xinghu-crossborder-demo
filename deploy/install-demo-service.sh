#!/usr/bin/env bash
set -euo pipefail

repo=/opt/xinghu-crossborder-demo
test -s /etc/global-role-intelligence/diagnosis-api-token
install -o root -g root -m 0644 "$repo/deploy/xinghu-crossborder-demo.service" /etc/systemd/system/xinghu-crossborder-demo.service
install -o root -g root -m 0644 "$repo/deploy/nginx/xinghu-crossborder-demo.conf" /etc/nginx/conf.d/xinghu-crossborder-demo.conf
nginx -t
systemctl daemon-reload
systemctl enable xinghu-crossborder-demo.service
systemctl restart xinghu-crossborder-demo.service
systemctl reload nginx
