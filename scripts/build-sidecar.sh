#!/bin/bash
set -e

# SageMate Sidecar Build Script
# Bundles Python backend into a single executable for Tauri.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🔧 SageMate Sidecar Build"
echo "=========================="

# Step 1: Build frontend
echo "📦 Step 1: Building frontend..."
cd "${PROJECT_ROOT}/frontend"
npm run build

# Step 2: Activate Python environment
echo "🐍 Step 2: Activating Python environment..."
cd "${PROJECT_ROOT}"
source .venv/bin/activate

# Keep local secrets out of the build without deleting the developer's .env.
if [ -f "${PROJECT_ROOT}/.env" ]; then
  echo "🔒 Found local .env; PyInstaller spec does not include it in bundled data."
fi

# Step 3: PyInstaller build
echo "📦 Step 3: Building Python sidecar with PyInstaller..."
pyinstaller \
  "${PROJECT_ROOT}/scripts/pyinstaller/sagemate.spec" \
  --clean \
  --noconfirm

# Step 4: Copy binary to Tauri binaries directory
echo "📂 Step 4: Copying binary to src-tauri/binaries/..."
mkdir -p "${PROJECT_ROOT}/src-tauri/binaries"

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
  TARGET="aarch64-apple-darwin"
elif [ "$ARCH" = "x86_64" ]; then
  TARGET="x86_64-apple-darwin"
else
  TARGET="unknown"
fi

SIDEcar_NAME="sagemate-server-${TARGET}"
cp "${PROJECT_ROOT}/dist/sagemate-server" "${PROJECT_ROOT}/src-tauri/binaries/${SIDEcar_NAME}"
chmod +x "${PROJECT_ROOT}/src-tauri/binaries/${SIDEcar_NAME}"

echo ""
echo "✅ Sidecar build complete!"
echo "   Binary: src-tauri/binaries/${SIDEcar_NAME}"
echo ""
echo "Next step: cd src-tauri && cargo tauri build"
