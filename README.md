# GModRTX

Private setup repository for Elijah's local Garry's Mod RTX Remix install.

This repository intentionally does **not** include Garry's Mod game files, Steam depots, RTX/NVIDIA runtime binaries, release archives, cache files, crash dumps, screenshots, saves, or logs. Those files remain only in the local `/home/elijah/projects/GModRTX` install folder.

## Local launch

```bash
./launch-gmod-rtx.sh
```

## Resolution sync

The launcher detects the primary monitor resolution at runtime and starts the x64 Garry's Mod executable with matching `-w` and `-h` launch options.

Overrides:

```bash
GMOD_RTX_RESOLUTION=2560x1440 ./launch-gmod-rtx.sh
GMOD_RTX_WIDTH=2560 GMOD_RTX_HEIGHT=1440 ./launch-gmod-rtx.sh
GMOD_RTX_SPAN_DESKTOP=1 ./launch-gmod-rtx.sh
```

## RTXLauncher UI

```bash
./open-rtxlauncher.sh
```

## Reinstall/update helper

```bash
./_tools/install_gmod_rtx.py
```

The helper expects a legitimate local Steam install of Garry's Mod and downloads upstream public release artifacts as needed.

## External requirements

- Steam account ownership/login for Garry's Mod
- Proton installed through Steam, preferably Proton Experimental
- GPU driver/Vulkan stack
