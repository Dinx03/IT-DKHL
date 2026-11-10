#!/usr/bin/env bash
# 02-load-schema.sh — ส่งสคีมาเข้า VM แล้วรัน DDL ตามลำดับ
#
# รันจาก Windows (Git Bash) ที่ไดเรกทอรีรากของรีโป:
#     bash growth/setup/02-load-schema.sh
#
# ไม่ต้องใช้ sudo — ต้องรัน 01-install-postgres.sh ให้จบก่อน
# รันซ้ำได้เฉพาะกับฐานข้อมูลเปล่า (DDL เป็น CREATE ไม่ใช่ CREATE IF NOT EXISTS)
# อยากล้างเริ่มใหม่:  bash growth/setup/02-load-schema.sh --reset

set -euo pipefail

VM="frappe@127.0.0.1"
PORT=2222
REMOTE=/tmp/growth-schema
LOCAL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/schema"

RESET=0
[ "${1:-}" = "--reset" ] && RESET=1

echo "==> ส่งไฟล์สคีมาเข้า VM"
ssh -p "$PORT" "$VM" "mkdir -p $REMOTE && rm -f $REMOTE/*.sql $REMOTE/*.json"
scp -P "$PORT" -q "$LOCAL"/*.sql "$LOCAL"/*.json "$VM:$REMOTE/"
ssh -p "$PORT" "$VM" "ls $REMOTE | tr '\n' ' '"

if [ "$RESET" = "1" ]; then
  echo ""
  echo "==> ล้าง schema public แล้วสร้างใหม่ (--reset)"
  ssh -p "$PORT" "$VM" 'source ~/growth.env && psql -h 127.0.0.1 -U "$GROWTH_DB_USER" "$GROWTH_DB_NAME" -q -c "drop schema public cascade; create schema public;"'
fi

echo ""
echo "==> รัน DDL ตามลำดับ (หยุดทันทีที่เจอ error)"
ssh -p "$PORT" "$VM" bash -s <<'REMOTE_SCRIPT'
set -euo pipefail
source ~/growth.env
cd /tmp/growth-schema
for f in $(ls *.sql | sort); do
  printf '    %-32s ' "$f"
  if out=$(psql -h 127.0.0.1 -U "$GROWTH_DB_USER" "$GROWTH_DB_NAME" \
             -v ON_ERROR_STOP=1 --quiet -f "$f" 2>&1); then
    echo "ok"
  else
    echo "ล้มเหลว"
    echo "$out" | sed 's/^/        /'
    exit 1
  fi
done
REMOTE_SCRIPT

echo ""
echo "==> สรุปสิ่งที่สร้างขึ้น"
ssh -p "$PORT" "$VM" 'source ~/growth.env && psql -h 127.0.0.1 -U "$GROWTH_DB_USER" "$GROWTH_DB_NAME" -q -c "
select
  (select count(*) from information_schema.tables  where table_schema=(select current_schema()) and table_type=(select '"'"'BASE TABLE'"'"')) as ตาราง,
  (select count(*) from pg_matviews where schemaname=current_schema())                       as matview,
  (select count(*) from pg_views   where schemaname=current_schema())                        as view,
  (select count(*) from policy_rules)                                                        as กฎ,
  (select count(*) from event_types)                                                         as event_type;"'
