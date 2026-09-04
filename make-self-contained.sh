#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLD_TOOLS="$SELF/_tools"
OLD_REPO="$SELF/_source/garrys-mod-rtx-remixed"

copy_link_target() {
  local link="$1"
  local target tmp parent base
  if [[ ! -L "$link" ]]; then
    return 0
  fi
  target="$(readlink -f "$link")"
  parent="$(dirname "$link")"
  base="$(basename "$link")"
  tmp="$parent/.${base}.selfcontained.$$"
  rm -rf "$tmp"
  if [[ -d "$target" ]]; then
    mkdir -p "$tmp"
    cp -a "$target/." "$tmp/"
  else
    cp -a "$target" "$tmp"
  fi
  rm "$link"
  mv "$tmp" "$link"
  printf 'materialized %s from %s\n' "$link" "$target"
}

printf '%s\n' 'Materializing external symlinks inside the GModRTX folder...'
while IFS= read -r -d '' link; do
  copy_link_target "$link"
done < <(find "$SELF" -type l -print0 | sort -z)

printf '%s\n' 'Copying tools and source snapshots into the GModRTX folder...'
mkdir -p "$SELF/_tools" "$SELF/_source"
printf 'Tools and source snapshots are already inside this folder.\n'

printf '%s\n' 'Writing self-contained launcher scripts...'
cat > "$SELF/launch-gmod-rtx.sh" <<'LAUNCH'
#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STEAM_ROOT="${STEAM_ROOT:-$HOME/.steam/steam}"
if [[ ! -d "$STEAM_ROOT" && -d "$HOME/.local/share/Steam" ]]; then
  STEAM_ROOT="$HOME/.local/share/Steam"
fi
COMPAT_DATA="${STEAM_COMPAT_DATA_PATH:-$STEAM_ROOT/steamapps/compatdata/4000}"
mkdir -p "$COMPAT_DATA"

find_proton() {
  if [[ -n "${PROTON_PATH:-}" && -x "$PROTON_PATH" ]]; then
    printf '%s\n' "$PROTON_PATH"
    return 0
  fi
  local candidate
  for candidate in \
    "$STEAM_ROOT/steamapps/common/Proton - Experimental/proton" \
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

PROTON="$(find_proton)" || {
  echo "Could not find Proton. Install Proton Experimental in Steam, or set PROTON_PATH=/path/to/proton." >&2
  exit 1
}

if command -v steam >/dev/null 2>&1; then
  steam -silent >/dev/null 2>&1 & disown || true
fi

printf '4000' > "$SELF/steam_appid.txt"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"
export STEAM_COMPAT_DATA_PATH="$COMPAT_DATA"
export WINEDLLOVERRIDES="d3d9=n,b${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"
export SteamAppId=4000
export SteamAppID=4000
export SteamGameId=4000
export SteamOverlayGameId=4000

if [[ -e /proc/driver/nvidia/version || -d /proc/driver/nvidia || -d /sys/module/nvidia ]]; then
  export WINE_DISABLE_HARDWARE_SCHEDULING=1
  export PROTON_HIDE_NVIDIA_GPU=0
  export PROTON_ENABLE_NVAPI=1
fi

cd "$SELF"
exec "$PROTON" run "$SELF/gmod.exe" \
  -game garrysmod \
  -console \
  -dxlevel 90 \
  +mat_disable_d3d9ex 1 \
  -nod3d9ex \
  -windowed \
  -noborder \
  -noworkshop \
  "$@"
LAUNCH
chmod +x "$SELF/launch-gmod-rtx.sh"

cat > "$SELF/open-rtxlauncher.sh" <<'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export XDG_DATA_HOME="$SELF/.local/share"
mkdir -p "$XDG_DATA_HOME/RTXLauncher"
cat > "$XDG_DATA_HOME/RTXLauncher/settings.xml" <<XML
<?xml version="1.0" encoding="utf-8"?>
<SettingsData xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" UseCustomResolution="false" Width="1920" Height="1080" LoadWorkshopAddons="false" DisableChromium="false" ConsoleEnabled="true" DeveloperMode="false" ToolsMode="false" DXLevel="90" CustomLaunchOptions="" ManuallySpecifiedInstallPath="$SELF" LinuxProtonPath="" LinuxSteamRootOverride="$HOME/.steam/steam" LinuxEnableProtonLog="false" LinuxSelectedProtonLabel="Proton - Experimental" LinuxVulkanDriver="Auto" LinuxCustomEnvironmentVariables="" LinuxLaunchCommandPrefix="" CheckForUpdatesOnLaunch="true" UseLocalInstallPath="false" Theme="Simple" SetupCompleted="true" CopyLauncherToInstallFolder="false" AddLauncherToStartMenu="false" />
XML
cd "$SELF/_tools/RTXLauncher-nightly"
exec ./RTXLauncher.Avalonia "$@"
LAUNCHER
chmod +x "$SELF/open-rtxlauncher.sh"

cat > "$SELF/run-gmod-rtx-via-rtxlauncher.sh" <<'RTXL'
#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SELF/open-rtxlauncher.sh" --skip-launcher
RTXL
chmod +x "$SELF/run-gmod-rtx-via-rtxlauncher.sh"

cat > "$SELF/README_SELF_CONTAINED.txt" <<README
GMod RTX self-contained folder
================================

Primary launch command:
  $SELF/launch-gmod-rtx.sh

Alternative RTXLauncher launch:
  $SELF/run-gmod-rtx-via-rtxlauncher.sh

Open RTXLauncher UI:
  $SELF/open-rtxlauncher.sh

This folder contains the copied Garry's Mod game files, RTX Remix runtime, GMod RTX fixes, SourceRTXTweaks patched binaries, tools, cached packages, and source snapshots used for setup.

Remaining external requirements:
  - Steam account ownership / Steam client
  - Proton installed through Steam, preferably Proton Experimental
  - GPU driver/Vulkan stack

The game data itself is no longer symlinked back to /home/elijah/.steam/steam/steamapps/common/GarrysMod.
README

mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/gmod-rtx.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=GMod RTX
Comment=Launch self-contained Garry's Mod RTX Remix
Exec=$SELF/launch-gmod-rtx.sh
Path=$SELF
Terminal=false
Categories=Game;
DESKTOP
chmod +x "$HOME/.local/share/applications/gmod-rtx.desktop"
cat > "$HOME/.local/share/applications/rtxlauncher-gmod.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=RTXLauncher for GMod RTX
Comment=Open RTXLauncher from the self-contained GMod RTX folder
Exec=$SELF/open-rtxlauncher.sh
Path=$SELF
Terminal=false
Categories=Game;
DESKTOP
chmod +x "$HOME/.local/share/applications/rtxlauncher-gmod.desktop"

printf '%s\n' 'Done.'
