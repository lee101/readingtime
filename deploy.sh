#!/bin/bash
# readingtime.app.nz: build, sync static to R2 (readingtimestatic), restart, purge Cloudflare.
set -e
cd /nvme0n1-disk/code/readingtime
export PATH="/usr/local/go/bin:$HOME/.bun/bin:$PATH"
G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; N='\033[0m'
FORCE=0; SYNC_ONLY=0
for a in "$@"; do [ "$a" = "--force" ] && FORCE=1; [ "$a" = "--sync-only" ] && SYNC_ONLY=1; done

envget() { grep -hE "^$1=" .env ../app-site/.env 2>/dev/null | head -1 | cut -d= -f2- | sed 's/^ *//'; }
for v in CLOUDFLARE_API_KEY CLOUDFLARE_EMAIL CLOUDFLARE_ZONE_APP_NZ; do [ -z "${!v}" ] && export "$v=$(envget $v)"; done

echo -e "${Y}Build${N}"
go vet ./... && go build -o readingtime .

BUCKET="${STATIC_BUCKET:-readingtimestatic}"
R2="${R2_ENDPOINT:-https://f76d25b8b86cfa5638f43016510d8f77.r2.cloudflarestorage.com}"
STATE=.deploy-state; mkdir -p $STATE
echo -e "${Y}Sync static -> s3://$BUCKET${N}"
FAIL=0
for d in css js img bower_components bookdata kids-book-covers manuscript-covers manuscript-pages educational-infographics docs; do
  [ -d static/$d ] || continue
  h=$(find static/$d -type f -print0 | sort -z | xargs -0 -r stat -c '%n %s %Y' | sha256sum | cut -d' ' -f1)
  if [ $FORCE = 0 ] && [ "$(cat $STATE/$d 2>/dev/null)" = "$h" ]; then echo "unchanged $d"; continue; fi
  if timeout 900 aws s3 sync static/$d s3://$BUCKET/static/$d --endpoint-url "$R2" \
      --cache-control "public, max-age=31536000, immutable" --size-only --only-show-errors \
      --exclude '*.map' --exclude '*.DS_Store' >$STATE/$d.log 2>&1; then
    echo "$h" >$STATE/$d; echo -e "${G}synced $d${N}"
  else
    echo -e "${R}sync failed $d${N}"; tail -2 $STATE/$d.log; FAIL=1
  fi
done
for f in css/app.css js/billing.js js/readingtime.js; do
  aws s3 cp static/$f s3://$BUCKET/static/$f --endpoint-url "$R2" --cache-control "public, max-age=3600" --only-show-errors || FAIL=1
done

if [ "$FAIL" = 1 ]; then echo -e "${R}static sync failed; not restarting${N}"; exit 1; fi

[ "$SYNC_ONLY" = 1 ] && { echo -e "${G}static synced (sync-only)${N}"; exit 0; }

if ! cmp -s systemd/readingtime.service /etc/systemd/system/readingtime.service 2>/dev/null; then
  sudo cp systemd/readingtime.service /etc/systemd/system/readingtime.service
  sudo systemctl daemon-reload; sudo systemctl enable readingtime.service
fi
if ! cmp -s nginx/readingtime.app.nz /etc/nginx/sites-available/readingtime.app.nz 2>/dev/null; then
  sudo cp nginx/readingtime.app.nz /etc/nginx/sites-available/readingtime.app.nz
  sudo ln -sf /etc/nginx/sites-available/readingtime.app.nz /etc/nginx/sites-enabled/readingtime.app.nz
  sudo nginx -t && sudo systemctl reload nginx
fi

echo -e "${Y}Restart${N}"
sudo systemctl restart readingtime.service
for i in $(seq 1 20); do
  curl -sf http://127.0.0.1:4337/health >/dev/null 2>&1 && { echo -e "${G}healthy${N}"; break; }
  [ "$i" -eq 20 ] && { echo -e "${R}not healthy${N}"; journalctl -u readingtime.service --no-pager -n 20; exit 1; }
  sleep 1
done

echo -e "${Y}Cloudflare purge${N}"
if [ -n "$CLOUDFLARE_API_KEY" ] && [ -n "$CLOUDFLARE_ZONE_APP_NZ" ]; then
  body='{"files":["https://readingtime.app.nz/","https://readingtime.app.nz/pricing","https://readingtime.app.nz/stories","https://readingtime.app.nz/sitemap.xml","https://readingtimestatic.app.nz/static/css/app.css","https://readingtimestatic.app.nz/static/js/billing.js","https://readingtimestatic.app.nz/static/js/readingtime.js"]}'
  ok=$(curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_APP_NZ/purge_cache" \
    -H "X-Auth-Email: ${CLOUDFLARE_EMAIL:-leepenkman@gmail.com}" -H "X-Auth-Key: $CLOUDFLARE_API_KEY" \
    -H "Content-Type: application/json" --data "$body" | python3 -c "import sys,json;print(json.load(sys.stdin).get('success'))")
  echo "purge success=$ok"
else
  echo -e "${Y}skipped (no Cloudflare creds)${N}"
fi
echo -e "${G}done: https://readingtime.app.nz${N}"
