#!/usr/bin/env bash
# 01-install-postgres.sh — ติดตั้ง PostgreSQL 18 + pgvector ใน VM เดียวกับ ERPNext
#
# รันในเครื่อง VM (ssh frappe@127.0.0.1 -p 2222) — ต้องใส่รหัส sudo ตอนรัน
# รันซ้ำได้ ไม่พังถ้าเคยรันแล้ว
#
# ทำไมลงใน VM แทนที่จะลงบน Windows:
#   - pgvector บน Windows ต้อง build เอง แต่ใน apt ของ Ubuntu มีให้พร้อม
#   - Docker Desktop ใช้ไม่ได้ (WSL ยังไม่ได้ติดตั้ง ต้องรีบูตเครื่อง)
#   - วันที่ย้ายขึ้น VPS จะเป็นขั้นตอนเดียวกันเป๊ะ ไม่ต้องเรียนใหม่

set -euo pipefail

DB_NAME=growth
DB_USER=growth
ENV_FILE="$HOME/growth.env"

echo "==> ตรวจนาฬิกาก่อน (นาฬิกาเพี้ยนทำให้ apt ปฏิเสธ release file)"
if ! timedatectl show -p NTPSynchronized --value | grep -q yes; then
  echo ""
  echo "  นาฬิกายังไม่ sync — apt จะล้มเหลวแบบอ่านไม่รู้เรื่อง"
  echo "  รัน  bash /tmp/00-fix-clock.sh  ก่อน แล้วค่อยกลับมารันไฟล์นี้"
  echo ""
  timedatectl | sed -n '1,5p'
  exit 1
fi
echo "    นาฬิกาปกติ: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

echo "==> ติดตั้ง postgresql-18 + pgvector"
sudo apt-get update -qq
sudo apt-get install -y -qq postgresql-18 postgresql-18-pgvector

echo "==> เปิดใช้งานและสตาร์ท"
sudo systemctl enable --now postgresql

echo "==> สร้าง role และ database"
if [ -f "$ENV_FILE" ]; then
  echo "    มี $ENV_FILE อยู่แล้ว ใช้รหัสเดิม"
  # shellcheck source=/dev/null
  source "$ENV_FILE"
else
  DB_PASS="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"
  umask 077
  cat > "$ENV_FILE" <<EOF
export GROWTH_DB_HOST=127.0.0.1
export GROWTH_DB_PORT=5432
export GROWTH_DB_NAME=$DB_NAME
export GROWTH_DB_USER=$DB_USER
export GROWTH_DB_PASS=$DB_PASS
export PGPASSWORD=\$GROWTH_DB_PASS
EOF
  chmod 600 "$ENV_FILE"
  echo "    สร้างรหัสใหม่ เก็บไว้ที่ $ENV_FILE (สิทธิ์ 600 ไม่อยู่ในรีโป)"
  source "$ENV_FILE"
fi

sudo -u postgres psql -v ON_ERROR_STOP=1 <<EOF
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$DB_USER') THEN
    CREATE ROLE $DB_USER LOGIN PASSWORD '$GROWTH_DB_PASS';
  ELSE
    ALTER ROLE $DB_USER LOGIN PASSWORD '$GROWTH_DB_PASS';
  END IF;
END
\$\$;
EOF

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
  sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
  echo "    สร้าง database $DB_NAME แล้ว"
else
  echo "    database $DB_NAME มีอยู่แล้ว"
fi

# extension ต้องสร้างโดย superuser
sudo -u postgres psql -d "$DB_NAME" -v ON_ERROR_STOP=1 -c \
  "CREATE EXTENSION IF NOT EXISTS pgcrypto; CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;"

echo "==> เปิดให้ต่อจากเครื่อง Windows ผ่าน port forward ของ VirtualBox"
PG_CONF="$(sudo -u postgres psql -tAc 'SHOW config_file')"
PG_HBA="$(sudo -u postgres psql -tAc 'SHOW hba_file')"
sudo sed -i "s/^#\?listen_addresses.*/listen_addresses = '*'/" "$PG_CONF"
if ! sudo grep -q "growth-platform" "$PG_HBA"; then
  echo "host    all    all    10.0.2.0/24    scram-sha-256    # growth-platform" | sudo tee -a "$PG_HBA" >/dev/null
fi
sudo systemctl restart postgresql

echo ""
echo "==> ตรวจผล"
sudo -u postgres psql -d "$DB_NAME" -c "SELECT version();" | head -3
sudo -u postgres psql -d "$DB_NAME" -c "\dx"

echo ""
echo "เสร็จแล้ว — ข้อมูลการต่อเก็บที่ $ENV_FILE"
echo "ทดสอบ:  source ~/growth.env && psql -h 127.0.0.1 -U growth growth -c 'select 1'"
