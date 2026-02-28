#!/usr/bin/env bash
set -euo pipefail

export LANG="${LANG:-ko_KR.UTF-8}"
export LC_ALL="${LC_ALL:-ko_KR.UTF-8}"
export LC_CTYPE="${LC_CTYPE:-ko_KR.UTF-8}"

CODEX_HOME="${CODEX_HOME:-/home/dev/.codex}"
COPY_MARKER="${CODEX_HOME}/.host_codex_copied_once"
OMX_PROJECT_DIR="${OMX_PROJECT_DIR:-/workspace/.omx}"
CODEX_CONFIG_FILE="${CODEX_HOME}/config.toml"

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

if [[ -f "${CODEX_CONFIG_FILE}" ]]; then
  if [[ -d "${OMX_PROJECT_DIR}/agents" ]]; then
    if grep -Eq 'config_file = "/Users/[^"]+/.omx/agents/' "${CODEX_CONFIG_FILE}"; then
      escaped_omx_dir="$(printf '%s' "${OMX_PROJECT_DIR}" | sed 's/[\/&]/\\&/g')"
      sed -E -i "s|config_file = \"/Users/[^\"]+/.omx/agents/([^\"]+)\"|config_file = \"${escaped_omx_dir}/agents/\\1\"|g" "${CODEX_CONFIG_FILE}"
      echo "[entrypoint] Rewrote OMX agent config paths to ${OMX_PROJECT_DIR}/agents."
    fi
  else
    echo "[entrypoint] WARNING: ${OMX_PROJECT_DIR}/agents not found; skipped OMX path rewrite."
  fi
fi

exec "$@"
