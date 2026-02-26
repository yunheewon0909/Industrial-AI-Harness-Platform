#!/usr/bin/env bash
set -euo pipefail

CODEX_HOME="${CODEX_HOME:-/home/dev/.codex}"
COPY_MARKER="${CODEX_HOME}/.host_codex_copied_once"

echo "[entrypoint] Starting OMX sandbox bootstrap..."

if [[ -n "${GIT_USER_NAME:-}" ]]; then
  git config --global user.name "${GIT_USER_NAME}"
fi
if [[ -n "${GIT_USER_EMAIL:-}" ]]; then
  git config --global user.email "${GIT_USER_EMAIL}"
fi

echo "[entrypoint] git user.name=$(git config --global --get user.name || true)"
echo "[entrypoint] git user.email=$(git config --global --get user.email || true)"

if [[ -S "${SSH_AUTH_SOCK:-}" ]]; then
  echo "[entrypoint] SSH agent socket detected: ${SSH_AUTH_SOCK}"
else
  echo "[entrypoint] WARNING: SSH_AUTH_SOCK is missing or not a socket."
fi

mkdir -p "${CODEX_HOME}"

if [[ -d /host-codex ]]; then
  if [[ ! -f "${COPY_MARKER}" ]]; then
    if [[ -n "$(ls -A /host-codex 2>/dev/null)" ]]; then
      cp -a --no-preserve=ownership /host-codex/. "${CODEX_HOME}/"
      touch "${COPY_MARKER}"
      echo "[entrypoint] Copied /host-codex (ro) to ${CODEX_HOME} (rw) once."
    else
      echo "[entrypoint] /host-codex exists but is empty."
    fi
  else
    echo "[entrypoint] ${CODEX_HOME} already initialized from /host-codex."
  fi
else
  echo "[entrypoint] WARNING: /host-codex mount not found."
fi

exec "$@"
