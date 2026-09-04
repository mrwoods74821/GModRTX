GMod RTX self-contained folder
================================

Primary launch command:
  /home/elijah/projects/GModRTX/launch-gmod-rtx.sh

Alternative RTXLauncher launch:
  /home/elijah/projects/GModRTX/run-gmod-rtx-via-rtxlauncher.sh

Open RTXLauncher UI:
  /home/elijah/projects/GModRTX/open-rtxlauncher.sh

This folder contains the copied Garry's Mod game files, RTX Remix runtime, GMod RTX fixes, SourceRTXTweaks patched binaries, tools, cached packages, and source snapshots used for setup.

Remaining external requirements:
  - Steam account ownership / Steam client
  - Proton installed through Steam, preferably Proton Experimental
  - GPU driver/Vulkan stack

The game data itself is no longer symlinked back to /home/elijah/.steam/steam/steamapps/common/GarrysMod.

Resolution sync
===============

launch-gmod-rtx.sh detects the current primary monitor resolution with xrandr and launches GMod with -w WIDTH -h HEIGHT in borderless-windowed mode. RTXLauncher settings are regenerated with the same width and height when open-rtxlauncher.sh is used.

Overrides:
  GMOD_RTX_RESOLUTION=2560x1440 ./launch-gmod-rtx.sh
  GMOD_RTX_WIDTH=2560 GMOD_RTX_HEIGHT=1440 ./launch-gmod-rtx.sh
  GMOD_RTX_SPAN_DESKTOP=1 ./launch-gmod-rtx.sh   # use the full X desktop canvas instead of primary monitor

