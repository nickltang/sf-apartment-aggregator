#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_PATH="$REPO_DIR/ops/com.nickltang.sf-apartment-aggregator.awake.plist"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_PATH="$TARGET_DIR/com.nickltang.sf-apartment-aggregator.awake.plist"
LABEL="com.nickltang.sf-apartment-aggregator.awake"

mkdir -p "$TARGET_DIR"
mkdir -p "$REPO_DIR/logs"

sed "s|__REPO_DIR__|$REPO_DIR|g" "$TEMPLATE_PATH" > "$TARGET_PATH"

launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$TARGET_PATH"
launchctl enable "gui/$(id -u)/$LABEL"
launchctl kickstart -k "gui/$(id -u)/$LABEL"

echo "Installed and started: $LABEL"
echo "plist: $TARGET_PATH"
