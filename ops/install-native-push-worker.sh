#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
SERVICE_SOURCE="$PROJECT_DIR/ops/systemd/pubchat-native-push.service"
TIMER_SOURCE="$PROJECT_DIR/ops/systemd/pubchat-native-push.timer"
SERVICE_TARGET="/etc/systemd/system/pubchat-native-push.service"
TIMER_TARGET="/etc/systemd/system/pubchat-native-push.timer"
PYTHON="$BACKEND_DIR/venv/bin/python3"

for file in "$SERVICE_SOURCE" "$TIMER_SOURCE" "$PYTHON"; do
  if [[ ! -e "$file" ]]; then
    echo "Missing native push rollout dependency: $file" >&2
    exit 1
  fi
done

cd "$BACKEND_DIR"

# Offline validation only: settings loads backend/.env, then the worker verifies
# project/email/private-key shape and RS256 signing without contacting Google.
if ! "$PYTHON" -m workers.native_push_delivery --check-config; then
  echo "Native push preflight failed; systemd timer was not changed." >&2
  exit 1
fi

sudo install -m 0644 "$SERVICE_SOURCE" "$SERVICE_TARGET"
sudo install -m 0644 "$TIMER_SOURCE" "$TIMER_TARGET"
sudo systemctl daemon-reload
sudo systemctl enable --now pubchat-native-push.timer

sudo systemctl status pubchat-native-push.timer --no-pager

echo "Native push worker installed."
echo "Next production proof: register a real Android FCM installation, opt in, go offline, and confirm delivery + /admin/operations native_push health."
