#!/usr/bin/env bash
# Toggle llama-server for a GGUF model on localhost:8080.
# Usage: ./llama_server.sh [start|stop|status|logs|toggle]   (default: toggle)
#
# Configure via env vars (or edit the defaults below):
#   MODEL     path to a .gguf file, OR a cute name (g40-04 / q35-09 / g40-26 /
#             q36-27). If empty, resolves via ~/enough/config/models.json
#             (the 'current' model selected by the user / installer).
#   HOST      bind address                   (default: 127.0.0.1)
#   PORT      server port                    (default: 8080)
#   NGL       GPU layers to offload          (default: 99 = all, Apple Metal)
#   CTX       TOTAL context across slots     (default: auto, sized from the
#             chosen model's ctx_defaults for this host's RAM; override with
#             a literal number)
#   PARALLEL  concurrent request slots       (default: 1)
#   SPEC      MTP speculative decoding       (default: auto = on for models
#             whose registry entry has an 'mtp' block AND the installed
#             llama.cpp release is new enough; SPEC=off disables)
#
# Examples:
#   ./llama_server.sh start                         # current model, auto ctx
#   MODEL=g40-04 ./llama_server.sh start            # cute name
#   MODEL=~/some/path.gguf CTX=8192 ./llama_server.sh start  # direct path
#   SPEC=off ./llama_server.sh start                # force MTP off

set -euo pipefail

MODEL="${MODEL:-}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
NGL="${NGL:-99}"
CTX="${CTX:-}"
PARALLEL="${PARALLEL:-1}"
SPEC="${SPEC:-auto}"

# Filled in by resolve_model for registry models with MTP heads.
SPEC_ARGS=""
SPEC_MIN_RELEASE=0

ENOUGH_HOME="$HOME/enough"
resolve_model() {
  # If MODEL contains '/', treat as a literal path; else resolve via the
  # models registry. If MODEL is empty, use the current cute-name from the
  # live config.
  local want="$1"
  if [[ "$want" == */* ]]; then
    MODEL_PATH="$want"
    # CTX stays as whatever caller set (or empty → llama-server default).
    return 0
  fi
  if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv not on PATH; can't resolve cute model name without it." >&2
    return 1
  fi
  local args=()
  if [[ -n "$want" ]]; then args+=(--cute "$want"); fi
  local out
  if ! out=$(uv run --project "$ENOUGH_HOME" python -m enough.models params "${args[@]}" 2>&1); then
    echo "error: could not resolve model: $out" >&2
    return 1
  fi
  eval "$out"  # sets MODEL_PATH, CTX_RECOMMENDED, MODEL_CUTE, MODEL_LABEL,
               # SPEC_ARGS, SPEC_MIN_RELEASE
  if [[ -z "${CTX}" ]]; then
    CTX="$CTX_RECOMMENDED"
  fi
}

llama_release() {
  # The numeric b-release of the installed llama.cpp, e.g. "9200".
  # Empty if unparseable (treat as too old).
  llama-server --version 2>&1 | sed -n 's/^version: \([0-9][0-9]*\).*/\1/p' | head -n 1
}

resolve_spec_flags() {
  # Decide the speculative-decoding flags for this launch. MTP drafts come
  # from head tensors inside the main GGUF, so this is just flags — but
  # only on a llama.cpp new enough to know them (older builds reject
  # unknown args at startup, which would look like a broken install).
  SPEC_FLAGS=""
  if [[ "$SPEC" == "off" || -z "$SPEC_ARGS" ]]; then
    return 0
  fi
  local rel
  rel="$(llama_release)"
  if [[ -n "$rel" && "$rel" -ge "$SPEC_MIN_RELEASE" ]]; then
    SPEC_FLAGS="$SPEC_ARGS"
  else
    echo "note: llama.cpp release ${rel:-unknown} < $SPEC_MIN_RELEASE — starting without MTP" >&2
    echo "      (brew upgrade llama.cpp to enable speculative decoding)" >&2
  fi
}

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
  if ! resolve_model "$MODEL"; then
    return 1
  fi
  if [[ ! -f "$MODEL_PATH" ]]; then
    echo "error: model file not found: $MODEL_PATH" >&2
    echo "       re-run bootstrap.sh to download it, or pass MODEL=<cute-name-of-an-installed-model>." >&2
    return 1
  fi
  mkdir -p "$STATE_DIR"
  resolve_spec_flags
  local ctx_to_use="${CTX:-32768}"
  echo "launching llama-server with:"
  echo "  model: $MODEL_PATH"
  echo "  ctx:   $ctx_to_use"
  echo "  mtp:   ${SPEC_FLAGS:-off}"
  # SPEC_FLAGS is deliberately unquoted: it's a space-separated flag
  # string (no values with spaces) that llama-server gets as N args.
  # shellcheck disable=SC2086
  nohup llama-server \
    -m "$MODEL_PATH" \
    --host "$HOST" --port "$PORT" \
    -ngl "$NGL" -c "$ctx_to_use" --parallel "$PARALLEL" --jinja \
    $SPEC_FLAGS \
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
