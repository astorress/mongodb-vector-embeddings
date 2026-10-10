######## BASE IMAGE ########
FROM mongo:8.2.12 AS mongo-base
FROM python:3.13-slim-trixie AS img-base

# Arguments
ARG USER=mongodb-vector-search
ARG USER_HOME=/home/$USER
ARG VOLUME=/app
ARG SHELL=/bin/bash

RUN pip3 install --upgrade pip

RUN apt-get update

# Inital OS configuration
RUN apt-get install -y locales \
    && sed -i 's/^# *\(en_US.UTF-8\)/\1/' /etc/locale.gen \
    && locale-gen
RUN apt-get install -y sudo git curl jq less procps

# MongoDB shell and database tools copied from the official image
COPY --from=mongo-base \
    /usr/bin/mongosh \
    /usr/bin/mongodump \
    /usr/bin/mongorestore \
    /usr/bin/mongoexport \
    /usr/bin/mongoimport \
    /usr/bin/mongostat \
    /usr/bin/mongotop \
    /usr/bin/
RUN mongosh --version

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


######## LAB IMAGE ########
FROM img-base AS img-lab

ARG USER=mongodb-vector-search

# Install VSCode extensions dependencies
RUN pip3 install pylint yapf isort

# CPU-only torch keeps the image small (PyPI's default wheel bundles CUDA on amd64)
RUN pip3 install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu

# Hugging Face models cache (embedding model), persisted in a named volume
ENV HF_HOME=/cache/huggingface
RUN mkdir -p $HF_HOME && chown -R $USER:$USER /cache

USER $USER
