#!/usr/bin/env bash
# Toggle llama-server for Gemma 4 26B MoE Q4_K_M on localhost:8080.
# Usage: ./llama_server.sh [start|stop|status|logs|toggle]   (default: toggle)

set -euo pipefail

MODEL="/Users/m3u/METMcloud/METMroot/tools/fmv/weights/gemma-root/gemma4-26b-gguf/gemma-4-26B-A4B-it-Q4_K_M.gguf"
HOST="127.0.0.1"
PORT="8080"
NGL="99"
CTX="8192"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="$SCRIPT_DIR/.llama-server"
LOG_FILE="$STATE_DIR/server.log"
PID_FILE="$STATE_DIR/server.pid"

is_running() {
  [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

start() {
  if is_running; then
    echo "already running (pid $(cat "$PID_FILE")) on $HOST:$PORT"
    return 0
  fi
  if ! command -v llama-server >/dev/null 2>&1; then
    echo "error: llama-server not found. install with: brew install llama.cpp" >&2
    return 1
  fi
  if [[ ! -f "$MODEL" ]]; then
    echo "error: model not found at $MODEL" >&2
    return 1
  fi
  mkdir -p "$STATE_DIR"
  nohup llama-server \
    -m "$MODEL" \
    --host "$HOST" --port "$PORT" \
    -ngl "$NGL" -c "$CTX" --jinja \
    >"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  disown
  echo "started pid=$(cat "$PID_FILE") on http://$HOST:$PORT  (log: $LOG_FILE)"
  echo "waiting for health..."
  for _ in $(seq 1 120); do
    if [[ "$(curl -s -o /dev/null -w '%{http_code}' "http://$HOST:$PORT/health" 2>/dev/null)" == "200" ]]; then
      echo "ready"
      return 0
    fi
    sleep 2
  done
  echo "warning: did not reach ready state within 240s (still loading or failed; check $LOG_FILE)" >&2
  return 1
}

stop() {
  if ! is_running; then
    echo "not running"
    rm -f "$PID_FILE"
    return 0
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
  if kill -0 "$pid" 2>/dev/null; then
    echo "graceful stop failed, sending SIGKILL to $pid"
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
  echo "stopped"
}

status() {
  if is_running; then
    echo "running (pid $(cat "$PID_FILE")) on http://$HOST:$PORT"
    curl -s "http://$HOST:$PORT/health" && echo
  else
    echo "not running"
  fi
}

case "${1:-toggle}" in
  start)   start ;;
  stop)    stop ;;
  status)  status ;;
  logs)    tail -f "$LOG_FILE" ;;
  toggle)  if is_running; then stop; else start; fi ;;
  *)       echo "usage: $0 [start|stop|status|logs|toggle]" >&2; exit 2 ;;
esac
