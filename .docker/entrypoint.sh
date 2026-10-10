#!/bin/bash

COLOR_MAGENTA=$(tput setaf 5)
COLOR_GREEN=$(tput setaf 2)
COLOR_BLUE=$(tput setaf 4)
COLOR_DEFAULT=$(tput sgr0)

STEP=1
STEP_COUNT=2

echo "${COLOR_MAGENTA}${STEP}/$STEP_COUNT:${COLOR_GREEN} Marking ${COLOR_BLUE}/app${COLOR_GREEN} as a safe git directory.${COLOR_DEFAULT}"
git config --global --add safe.directory /app
let STEP++

echo "${COLOR_MAGENTA}${STEP}/$STEP_COUNT:${COLOR_GREEN} Downloading embedding model ${COLOR_BLUE}$EMBEDDING_MODEL${COLOR_GREEN} (cached after the first run).${COLOR_DEFAULT}"
python -c "from rag.embeddings import get_model; get_model()"
let STEP++

echo "$COLOR_DEFAULT"
