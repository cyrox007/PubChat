#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
SERVICE_SOURCE="$PROJECT_DIR/ops/systemd/pubchat-e2ee-attachment-retention.service"
TIMER_SOURCE="$PROJECT_DIR/ops/systemd/pubchat-e2ee-attachment-retention.timer"
SERVICE_TARGET="/etc/systemd/system/pubchat-e2ee-attachment-retention.service"
TIMER_TARGET="/etc/systemd/system/pubchat-e2ee-attachment-retention.timer"

for file in "$SERVICE_SOURCE" "$TIMER_SOURCE"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing E2EE attachment retention unit: $file" >&2
    exit 1
  fi
done

cd "$BACKEND_DIR"
"$BACKEND_DIR/venv/bin/python3" - <<'PY'
# settings loads backend/.env before the attachment module resolves its root.
from settings import config  # noqa: F401
from components.message.e2ee_attachment import E2EE_ATTACHMENT_STORAGE_ROOT
from components.message.e2ee_attachment_retention import (
    orphan_grace_hours,
    pending_retention_hours,
    retention_batch_size,
)

root = E2EE_ATTACHMENT_STORAGE_ROOT
root.mkdir(parents=True, exist_ok=True, mode=0o700)
root.chmod(0o700)
print(
    "E2EE attachment retention settings: OK "
    f"(root={root}, pending_hours={pending_retention_hours()}, "
    f"orphan_hours={orphan_grace_hours()}, batch_size={retention_batch_size()})"
)
PY

# Validate database/storage access without deleting anything before installing units.
"$BACKEND_DIR/venv/bin/python3" -m workers.e2ee_attachment_retention --dry-run

sudo install -m 0644 "$SERVICE_SOURCE" "$SERVICE_TARGET"
sudo install -m 0644 "$TIMER_SOURCE" "$TIMER_TARGET"
sudo systemctl daemon-reload
sudo systemctl enable --now pubchat-e2ee-attachment-retention.timer

# Run one bounded retention cycle so systemd/runtime permission problems are visible now.
if ! sudo systemctl start pubchat-e2ee-attachment-retention.service; then
  echo "PubChat E2EE attachment retention worker failed its first run." >&2
  sudo systemctl status pubchat-e2ee-attachment-retention.service --no-pager || true
  sudo journalctl -u pubchat-e2ee-attachment-retention.service -n 120 --no-pager || true
  exit 1
fi

sudo systemctl status pubchat-e2ee-attachment-retention.timer --no-pager
sudo systemctl status pubchat-e2ee-attachment-retention.service --no-pager || true
