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
    locales \
    openssh-client \
    python3 \
    python3-venv \
    tmux \
    && sed -i 's/^# *\(en_US.UTF-8 UTF-8\)/\1/' /etc/locale.gen \
    && sed -i 's/^# *\(ko_KR.UTF-8 UTF-8\)/\1/' /etc/locale.gen \
    && locale-gen en_US.UTF-8 ko_KR.UTF-8 \
    && update-locale LANG=ko_KR.UTF-8 LC_ALL=ko_KR.UTF-8 \
    && ln -sf /usr/bin/python3 /usr/local/bin/python \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN echo "NPM_REFRESH=${NPM_REFRESH}" \
    && npm install -g "@openai/codex@${CODEX_NPM_TAG}" "oh-my-codex@${OMX_NPM_TAG}"

RUN useradd -m -s /bin/bash dev

ENV LANG=ko_KR.UTF-8
ENV LC_ALL=ko_KR.UTF-8
ENV CODEX_HOME=/home/dev/.codex
WORKDIR /workspace

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /workspace /home/dev/.codex \
    && chown -R dev:dev /workspace /home/dev

USER dev
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
