######## BASE IMAGE ########
FROM python:3.13-slim-bookworm AS python-base
FROM node:24-bookworm-slim AS img-base

# Arguments
ARG USER=vector-embeddings
ARG USER_HOME=/home/$USER
ARG VOLUME=/app
ARG SHELL=/bin/bash

COPY --from=python-base /usr/local/ /usr/local/
RUN ldconfig
RUN pip3 install --upgrade pip

RUN apt-get update
RUN npm install -g npm

# Inital OS configuration
RUN apt-get install -y locales \
    && sed -i 's/^# *\(en_US.UTF-8\)/\1/' /etc/locale.gen \
    && locale-gen
RUN apt-get install -y sudo lsb-release git curl zip unzip jq less

# Install CLI utilities
RUN npm install -g mongosh@2.13.0
RUN npm install -g @anthropic-ai/claude-code \
    && node "$(npm root -g)/@anthropic-ai/claude-code/install.cjs" \
    && claude --version

# Set up non root user
RUN echo "$USER ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
RUN useradd -ms $SHELL $USER
RUN mkdir -p $VOLUME \
    && chown -R $USER:$USER $VOLUME

# Preserve bash history
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
    && echo $SNIPPET >> "/root/.bashrc" \
    && mkdir /commandhistory \
    && touch /commandhistory/.bash_history \
    && chown -R $USER /commandhistory \
    && echo $SNIPPET >> "$USER_HOME/.bashrc"

# Let non-root user self-update global npm packages (mongosh, claude-code) at runtime
RUN chown -R $USER:$USER /usr/local/lib/node_modules /usr/local/bin


######## RAG IMAGE ########
FROM img-base AS img-rag

ARG USER=vector-embeddings

# Install VSCode extensions dependencies
RUN pip3 install pylint yapf isort

# Install Test utilities
RUN pip3 install pytest

# CPU-only torch keeps the image small (PyPI's default wheel bundles CUDA on amd64)
RUN pip3 install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt

# Make /app/src importable (python -m rag.<module>)
RUN echo "/app/src" > /usr/local/lib/python3.13/site-packages/rag.pth

# Hugging Face models cache, persisted in a named volume
ENV HF_HOME=/cache/huggingface
RUN mkdir -p $HF_HOME && chown -R $USER:$USER /cache

USER $USER
