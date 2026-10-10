#!/bin/bash

COLOR_GREEN=$(tput setaf 2)
COLOR_BLUE=$(tput setaf 4)
COLOR_DEFAULT=$(tput sgr0)

EXEC_PATH=$(dirname $(readlink -f "$0"))
ENVS_PATH=$EXEC_PATH/../.envs
MONGO_ENV=$ENVS_PATH/mongo.env

# Generate .envs/mongo.env once, with random passwords
if [ ! -f "$MONGO_ENV" ]; then
    PASSWORD=$(openssl rand -hex 16)
    cat > "$MONGO_ENV" <<EOF
MONGODB_INITDB_ROOT_USERNAME=root
MONGODB_INITDB_ROOT_PASSWORD=$PASSWORD
MONGODB_URI=mongodb://root:$PASSWORD@vector_embeddings_database:27017/?directConnection=true&authSource=admin
MONGODB_DATABASE=quijote
EMBEDDING_MODEL=intfloat/multilingual-e5-small
EOF
    echo "${COLOR_GREEN}File ${COLOR_BLUE}.envs/mongo.env${COLOR_GREEN} generated.${COLOR_DEFAULT}"
else
    echo "${COLOR_GREEN}File ${COLOR_BLUE}.envs/mongo.env${COLOR_GREEN} found! Skipping generation.${COLOR_DEFAULT}"
fi
