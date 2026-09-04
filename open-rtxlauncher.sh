#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

detect_resolution() {
  if [[ -n "${GMOD_RTX_WIDTH:-}" && -n "${GMOD_RTX_HEIGHT:-}" ]]; then
    printf '%s %s\n' "$GMOD_RTX_WIDTH" "$GMOD_RTX_HEIGHT"
    return 0
  fi
  if [[ "${GMOD_RTX_RESOLUTION:-}" =~ ^([0-9]+)x([0-9]+)$ ]]; then
    printf '%s %s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
    return 0
  fi
  if command -v xrandr >/dev/null 2>&1; then
    local xr line
    xr="$(xrandr --current 2>/dev/null || true)"
    if [[ "${GMOD_RTX_SPAN_DESKTOP:-0}" == "1" ]]; then
      line="$(printf '%s\n' "$xr" | awk '/^Screen 0:/ {for (i=1;i<=NF;i++) if ($i=="current") {gsub(",","",$(i+1)); print $(i+1)"x"$(i+3); exit}}')"
      if [[ "$line" =~ ^([0-9]+)x([0-9]+)$ ]]; then
        printf '%s %s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
        return 0
      fi
    fi
    line="$(printf '%s\n' "$xr" | awk '/ connected primary / {print; exit}')"
    if [[ -z "$line" ]]; then
      line="$(printf '%s\n' "$xr" | awk '/ connected / {print; exit}')"
    fi
    if [[ "$line" =~ ([0-9]+)x([0-9]+)\+[0-9]+\+[0-9]+ ]]; then
      printf '%s %s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
      return 0
    fi
  fi
  if command -v xdpyinfo >/dev/null 2>&1; then
    local dims
    dims="$(xdpyinfo 2>/dev/null | awk '/dimensions:/ {print $2; exit}')"
    if [[ "$dims" =~ ^([0-9]+)x([0-9]+)$ ]]; then
      printf '%s %s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
      return 0
    fi
  fi
  printf '1920 1080\n'
}

read -r WIDTH HEIGHT < <(detect_resolution)
export XDG_DATA_HOME="$SELF/.local/share"
mkdir -p "$XDG_DATA_HOME/RTXLauncher"
cat > "$XDG_DATA_HOME/RTXLauncher/settings.xml" <<XML
<?xml version="1.0" encoding="utf-8"?>
<SettingsData xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" UseCustomResolution="true" Width="$WIDTH" Height="$HEIGHT" LoadWorkshopAddons="false" DisableChromium="false" ConsoleEnabled="true" DeveloperMode="false" ToolsMode="false" DXLevel="90" CustomLaunchOptions="-w $WIDTH -h $HEIGHT" ManuallySpecifiedInstallPath="$SELF" LinuxProtonPath="" LinuxSteamRootOverride="$HOME/.steam/steam" LinuxEnableProtonLog="false" LinuxSelectedProtonLabel="Proton - Experimental" LinuxVulkanDriver="Auto" LinuxCustomEnvironmentVariables="" LinuxLaunchCommandPrefix="" CheckForUpdatesOnLaunch="true" UseLocalInstallPath="false" Theme="Simple" SetupCompleted="true" CopyLauncherToInstallFolder="false" AddLauncherToStartMenu="false" />
XML
cd "$SELF/_tools/RTXLauncher-nightly"
exec ./RTXLauncher.Avalonia "$@"
