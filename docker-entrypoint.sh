#!/bin/bash
set -e

# Remove stale Neo4j PID file if it exists
if [ -f /var/lib/neo4j/run/neo4j.pid ]; then
    rm -f /var/lib/neo4j/run/neo4j.pid
fi

# Start Neo4j
exec /sbin/tini -g -- /startup/docker-entrypoint.sh neo4j console
