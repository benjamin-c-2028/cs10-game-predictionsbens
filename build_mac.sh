#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

APP_NAME="Bitcoin-Up-or-Down-Arcade"
ENTRY_FILE="game.py"
PYTHON_CMD="${PYTHON:-python3}"

"$PYTHON_CMD" -m venv .venv-build
source .venv-build/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

rm -rf "build/$APP_NAME" "dist/$APP_NAME" "dist/$APP_NAME.app" "dist/$APP_NAME-macOS.zip"

python -m PyInstaller \
    --noconfirm \
    --clean \
    --windowed \
    --name "$APP_NAME" \
    --add-data "asset-game:asset-game" \
    "$ENTRY_FILE"

ARCADE_VERSION_PATH="dist/$APP_NAME.app/Contents/Resources/arcade/VERSION"
if [[ -f "$ARCADE_VERSION_PATH/VERSION" ]]; then
    tmp_version_file="$(mktemp)"
    cp "$ARCADE_VERSION_PATH/VERSION" "$tmp_version_file"
    rm -rf "$ARCADE_VERSION_PATH"
    mv "$tmp_version_file" "$ARCADE_VERSION_PATH"
    chmod 644 "$ARCADE_VERSION_PATH"
fi

codesign --force --deep --sign - "dist/$APP_NAME.app"

ditto -c -k --norsrc --keepParent "dist/$APP_NAME.app" "dist/$APP_NAME-macOS.zip"

echo
echo "Built dist/$APP_NAME.app"
echo "Built dist/$APP_NAME-macOS.zip"
