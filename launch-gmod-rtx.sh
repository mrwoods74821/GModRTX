#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STEAM_ROOT="${STEAM_ROOT:-$HOME/.steam/steam}"
if [[ ! -d "$STEAM_ROOT" && -d "$HOME/.local/share/Steam" ]]; then
  STEAM_ROOT="$HOME/.local/share/Steam"
fi
COMPAT_DATA="${STEAM_COMPAT_DATA_PATH:-$STEAM_ROOT/steamapps/compatdata/4000}"
LOG_DIR="$SELF/_logs"
mkdir -p "$COMPAT_DATA" "$LOG_DIR"

find_proton() {
  if [[ -n "${PROTON_PATH:-}" && -x "$PROTON_PATH" ]]; then
    printf '%s\n' "$PROTON_PATH"
    return 0
  fi
  local candidate
  for candidate in \
    "$STEAM_ROOT/steamapps/common/Proton - Experimental/proton" \
    "$STEAM_ROOT/steamapps/common/Proton Hotfix/proton" \
    "$STEAM_ROOT/steamapps/common/Proton - Hotfix/proton"; do
    if [[ -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  while IFS= read -r -d '' candidate; do
    printf '%s\n' "$candidate"
    return 0
  done < <(find \
    "$STEAM_ROOT/steamapps/common" \
    "$STEAM_ROOT/compatibilitytools.d" \
    "$HOME/.local/share/Steam/compatibilitytools.d" \
    "$HOME/.steam/root/compatibilitytools.d" \
    "$HOME/.steam/steam/compatibilitytools.d" \
    -maxdepth 3 -type f -name proton -path '*/Proton*/*' -print0 2>/dev/null | sort -zr)
  return 1
}

detect_resolution() {
  if [[ -n "${GMOD_RTX_WIDTH:-}" && -n "${GMOD_RTX_HEIGHT:-}" ]]; then
    printf '%s %s manual-env\n' "$GMOD_RTX_WIDTH" "$GMOD_RTX_HEIGHT"
    return 0
  fi
  if [[ "${GMOD_RTX_RESOLUTION:-}" =~ ^([0-9]+)x([0-9]+)$ ]]; then
    printf '%s %s manual-env\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
    return 0
  fi

  if command -v xrandr >/dev/null 2>&1; then
    local xr line res
    xr="$(xrandr --current 2>/dev/null || true)"
    if [[ "${GMOD_RTX_SPAN_DESKTOP:-0}" == "1" ]]; then
      line="$(printf '%s\n' "$xr" | awk '/^Screen 0:/ {for (i=1;i<=NF;i++) if ($i=="current") {gsub(",","",$(i+1)); print $(i+1)"x"$(i+3); exit}}')"
      if [[ "$line" =~ ^([0-9]+)x([0-9]+)$ ]]; then
        printf '%s %s xrandr-desktop\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
        return 0
      fi
    fi
    line="$(printf '%s\n' "$xr" | awk '/ connected primary / {print; exit}')"
    if [[ -z "$line" ]]; then
      line="$(printf '%s\n' "$xr" | awk '/ connected / {print; exit}')"
    fi
    if [[ "$line" =~ ([0-9]+)x([0-9]+)\+[0-9]+\+[0-9]+ ]]; then
      printf '%s %s xrandr-primary\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
      return 0
    fi
  fi

  if command -v xdpyinfo >/dev/null 2>&1; then
    local dims
    dims="$(xdpyinfo 2>/dev/null | awk '/dimensions:/ {print $2; exit}')"
    if [[ "$dims" =~ ^([0-9]+)x([0-9]+)$ ]]; then
      printf '%s %s xdpyinfo\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
      return 0
    fi
  fi

  printf '1920 1080 fallback\n'
}

write_video_settings() {
  local width="$1" height="$2" cfg="$SELF/garrysmod/cfg/video.txt"
  mkdir -p "$(dirname "$cfg")"
  cat > "$cfg" <<VIDEO
"VideoConfig"
{
	"setting.defaultres"		"$width"
	"setting.defaultresheight"		"$height"
	"setting.fullscreen"		"0"
	"setting.nowindowborder"		"1"
}
VIDEO
}

PROTON="$(find_proton)" || {
  echo "Could not find Proton. Install Proton Experimental in Steam, or set PROTON_PATH=/path/to/proton." >&2
  exit 1
}

GAME_EXE="$SELF/bin/win64/gmod.exe"
if [[ ! -f "$GAME_EXE" ]]; then
  echo "Missing x64 Garry's Mod executable: $GAME_EXE" >&2
  exit 1
fi

read -r WIDTH HEIGHT RES_SOURCE < <(detect_resolution)
write_video_settings "$WIDTH" "$HEIGHT"

if [[ "${GMOD_RTX_DRY_RUN:-0}" == "1" ]]; then
  echo "dry_run=1"
  echo "SELF=$SELF"
  echo "STEAM_ROOT=$STEAM_ROOT"
  echo "COMPAT_DATA=$COMPAT_DATA"
  echo "PROTON=$PROTON"
  echo "GAME_EXE=$GAME_EXE"
  echo "GAME_EXE_FILE=$(file -b "$GAME_EXE" 2>/dev/null || true)"
  echo "RTX_D3D9=$SELF/bin/win64/d3d9.dll"
  echo "RTX_D3D9_FILE=$(file -b "$SELF/bin/win64/d3d9.dll" 2>/dev/null || true)"
  echo "RESOLUTION=${WIDTH}x${HEIGHT}"
  echo "RESOLUTION_SOURCE=$RES_SOURCE"
  echo "VIDEO_CFG=$SELF/garrysmod/cfg/video.txt"
  exit 0
fi

steam_is_running() {
  pgrep -u "$(id -u)" -x steam >/dev/null 2>&1 && return 0
  pgrep -u "$(id -u)" -x steamwebhelper >/dev/null 2>&1 && return 0
  pgrep -u "$(id -u)" -f '[s]team-runtime|[s]teamwebhelper|ubuntu12_32/[s]team' >/dev/null 2>&1 && return 0
  return 1
}

if ! steam_is_running && command -v steam >/dev/null 2>&1; then
  echo "Steam is not running; starting Steam first..."
  steam -silent >/dev/null 2>&1 & disown || true
  for _ in {1..60}; do
    steam_is_running && break
    sleep 1
  done
fi

if ! steam_is_running; then
  echo "Steam does not appear to be running. Start/log into Steam, then run this script again." >&2
  echo "This self-contained install still needs Steam ownership/session services for appid 4000." >&2
  exit 1
fi

printf '4000' > "$SELF/steam_appid.txt"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
export STEAM_COMPAT_DATA_PATH="$COMPAT_DATA"
export WINEDLLOVERRIDES="d3d9=n,b${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"
export SteamAppId=4000
export SteamAppID=4000
export SteamGameId=4000
export SteamOverlayGameId=4000
export PROTON_LOG="${PROTON_LOG:-1}"
export PROTON_LOG_DIR="$LOG_DIR"

if [[ -e /proc/driver/nvidia/version || -d /proc/driver/nvidia || -d /sys/module/nvidia ]]; then
  export WINE_DISABLE_HARDWARE_SCHEDULING=1
  export PROTON_HIDE_NVIDIA_GPU=0
  export PROTON_ENABLE_NVAPI=1
fi

RUN_LOG="$LOG_DIR/run-$(date +%Y%m%d-%H%M%S).log"
{
  echo "GMod RTX launch $(date --iso-8601=seconds)"
  echo "SELF=$SELF"
  echo "STEAM_ROOT=$STEAM_ROOT"
  echo "COMPAT_DATA=$COMPAT_DATA"
  echo "PROTON=$PROTON"
  echo "GAME_EXE=$GAME_EXE"
  echo "RESOLUTION=${WIDTH}x${HEIGHT}"
  echo "RESOLUTION_SOURCE=$RES_SOURCE"
  echo "ARGS=-game garrysmod -console -dxlevel 90 +mat_disable_d3d9ex 1 -nod3d9ex -windowed -noborder -w $WIDTH -h $HEIGHT -noworkshop $*"
} | tee "$RUN_LOG"

cd "$SELF"
exec "$PROTON" run "$GAME_EXE" \
  -game garrysmod \
  -console \
  -dxlevel 90 \
  +mat_disable_d3d9ex 1 \
  -nod3d9ex \
  -windowed \
  -noborder \
  -w "$WIDTH" \
  -h "$HEIGHT" \
  -noworkshop \
  "$@"
