#!/bin/bash
# LEGION MISSION: HARD PANDORA RUN
APPID=489830
STEAM_ROOT="$HOME/.steam/steam"
[ ! -d "$STEAM_ROOT" ] && STEAM_ROOT="$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"
export STEAM_COMPAT_DATA_PATH="/media/paul-kane/SteamGames/steamapps/compatdata/$APPID"
export STEAM_COMPAT_CLIENT_INSTALL_PATH="$STEAM_ROOT"

COMMON_DIR="$STEAM_ROOT/steamapps/common"
PROTON_DIR="$COMMON_DIR/Proton - Experimental"
PROTON_BIN="$PROTON_DIR/proton"

PANDORA_EXE="/media/paul-kane/SteamGames/Games/mods/Pandora Behaviour Engine Standalone Windows x64/Pandora Behaviour Engine+.exe"
OUTPUT_DIR="/media/paul-kane/SteamGames/Games/mods/Pandora_Output"

echo "Executing Imperial Decree: Rebuild Behavior Graph..."
"$PROTON_BIN" run "$PANDORA_EXE" --cli --output "$OUTPUT_DIR"
