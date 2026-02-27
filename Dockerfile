FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG CODEX_NPM_TAG=latest
ARG OMX_NPM_TAG=latest
ARG NPM_REFRESH=0

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    openssh-client \
    tmux \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN echo "NPM_REFRESH=${NPM_REFRESH}" \
    && npm install -g "@openai/codex@${CODEX_NPM_TAG}" "oh-my-codex@${OMX_NPM_TAG}"

RUN useradd -m -s /bin/bash dev

ENV CODEX_HOME=/home/dev/.codex
WORKDIR /workspace

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /workspace /home/dev/.codex \
    && chown -R dev:dev /workspace /home/dev

USER dev
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
