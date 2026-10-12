#!/usr/bin/env bash
# Download pinned pandoc + tectonic into .tools/ (gitignored). No Homebrew.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/.tools"
PANDOC_VER="3.12.1"
TECTONIC_VER="0.17.0"
OS="$(uname -s)"
ARCH="$(uname -m)"

mkdir -p "$TOOLS"

download() {
  local url="$1"
  local dest="$2"
  echo "fetch $url"
  curl -fL --retry 3 --retry-delay 2 -o "$dest" "$url"
}

case "$OS/$ARCH" in
  Darwin/arm64)
    PANDOC_URL="https://github.com/jgm/pandoc/releases/download/${PANDOC_VER}/pandoc-${PANDOC_VER}-arm64-macOS.zip"
    TECTONIC_URL="https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VER}/tectonic-${TECTONIC_VER}-aarch64-apple-darwin.tar.gz"
    ;;
  Darwin/x86_64)
    PANDOC_URL="https://github.com/jgm/pandoc/releases/download/${PANDOC_VER}/pandoc-${PANDOC_VER}-x86_64-macOS.zip"
    TECTONIC_URL="https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VER}/tectonic-${TECTONIC_VER}-x86_64-apple-darwin.tar.gz"
    ;;
  Linux/x86_64)
    PANDOC_URL="https://github.com/jgm/pandoc/releases/download/${PANDOC_VER}/pandoc-${PANDOC_VER}-linux-amd64.tar.gz"
    TECTONIC_URL="https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VER}/tectonic-${TECTONIC_VER}-x86_64-unknown-linux-gnu.tar.gz"
    ;;
  Linux/aarch64|Linux/arm64)
    PANDOC_URL="https://github.com/jgm/pandoc/releases/download/${PANDOC_VER}/pandoc-${PANDOC_VER}-linux-arm64.tar.gz"
    TECTONIC_URL="https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VER}/tectonic-${TECTONIC_VER}-aarch64-unknown-linux-musl.tar.gz"
    ;;
  *)
    echo "unsupported platform: $OS/$ARCH" >&2
    exit 1
    ;;
esac

TMP="$(mktemp -d "${TMPDIR:-/tmp}/dracina-tools.XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

# Pandoc
rm -rf "$TOOLS/pandoc"
mkdir -p "$TOOLS/pandoc"
if [[ "$PANDOC_URL" == *.zip ]]; then
  download "$PANDOC_URL" "$TMP/pandoc.zip"
  unzip -q "$TMP/pandoc.zip" -d "$TMP/pandoc-src"
else
  download "$PANDOC_URL" "$TMP/pandoc.tar.gz"
  mkdir -p "$TMP/pandoc-src"
  tar -xzf "$TMP/pandoc.tar.gz" -C "$TMP/pandoc-src"
fi
PANDOC_BIN="$(find "$TMP/pandoc-src" -type f -name pandoc | head -n 1)"
if [[ -z "$PANDOC_BIN" ]]; then
  echo "pandoc binary missing from archive" >&2
  exit 1
fi
mkdir -p "$TOOLS/pandoc/bin"
cp "$PANDOC_BIN" "$TOOLS/pandoc/bin/pandoc"
chmod +x "$TOOLS/pandoc/bin/pandoc"

# Tectonic
rm -rf "$TOOLS/tectonic"
mkdir -p "$TOOLS/tectonic"
download "$TECTONIC_URL" "$TMP/tectonic.tar.gz"
tar -xzf "$TMP/tectonic.tar.gz" -C "$TMP"
TECTONIC_BIN="$(find "$TMP" -type f -name tectonic | head -n 1)"
if [[ -z "$TECTONIC_BIN" ]]; then
  echo "tectonic binary missing from archive" >&2
  exit 1
fi
cp "$TECTONIC_BIN" "$TOOLS/tectonic/tectonic"
chmod +x "$TOOLS/tectonic/tectonic"

echo "pandoc: $("$TOOLS/pandoc/bin/pandoc" --version | head -n 1)"
echo "tectonic: $("$TOOLS/tectonic/tectonic" --version | head -n 1)"
echo "tools ready under $TOOLS"
