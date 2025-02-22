#!/bin/bash
command=$(echo $@ | envsubst)

if [[ "$ENVIRONMENT" != "test" ]]; then
    # Wait for the PostgreSQL service to be ready
    /usr/bin/wait-for-it.sh $POSTGRES_HOST:$POSTGRES_PORT
fi
echo "Running command:"
echo "$command"
bash -c "$command"
