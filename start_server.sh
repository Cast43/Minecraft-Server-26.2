#!/usr/bin/env bash
set -euo pipefail

ROOT="/workspaces/Minecraft-Server-26.2"
CRAFTY_SCRIPT="$ROOT/Rminecraft/run_crafty.sh"
PLAYIT_DIR="playit-terminal"

if [ ! -f "$CRAFTY_SCRIPT" ]; then
  echo "Erro: script do Crafty não encontrado em $CRAFTY_SCRIPT"
  exit 1
fi

start_in_terminal() {
  local title="$1"
  local command_line="$2"
  local log_file="/tmp/${title}.log"

  echo "Iniciando $title em segundo plano..."
  nohup bash -lc "$command_line" >"$log_file" 2>&1 &
  echo "Processo $title iniciado; log: $log_file"
  return 0
}

if pgrep -f "$CRAFTY_SCRIPT" >/dev/null 2>&1; then
  echo "O Crafty já está em execução."
else
  echo "Iniciando Crafty..."
  start_in_terminal "crafty" "cd '$ROOT' && bash '$CRAFTY_SCRIPT'"
fi

if pgrep -f "$PLAYIT_DIR" >/dev/null 2>&1; then
  echo "O Playit já está em execução."
else
  echo "Iniciando Playit..."
  start_in_terminal "playit" "./playit-terminal"
fi
