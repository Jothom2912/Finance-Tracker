#!/bin/bash
# Load Neo4j database from dump file

set -e

DUMP_DIR="../dumps/neo4j"
CONTAINER_NAME="finance-neo4j"
DUMP_FILE="$DUMP_DIR/neo4j.dump"

echo "============================================================"
echo "📥 Neo4j Load Script"
echo "============================================================"

# Check if dump file exists
if [ ! -f "$DUMP_FILE" ]; then
    echo "❌ Dump file not found: $DUMP_FILE"
    exit 1
fi

echo "✅ Dump file found: $DUMP_FILE"

# Check if container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Container '$CONTAINER_NAME' is not running!"
    echo "   Start it with: docker-compose up -d neo4j"
    exit 1
fi

echo "✅ Container '$CONTAINER_NAME' is running"

# Copy dump to container
echo "📋 Copying dump to container..."
docker cp "$DUMP_FILE" "$CONTAINER_NAME:/dumps/neo4j.dump"

# Stop Neo4j (required for load)
echo "🛑 Stopping Neo4j..."
docker exec "$CONTAINER_NAME" neo4j stop || true

# Wait a moment
sleep 2

# Load dump
echo "📥 Loading dump..."
docker exec "$CONTAINER_NAME" neo4j-admin database load neo4j \
    --from-path=/dumps/neo4j.dump \
    --overwrite-destination=true

# Start Neo4j
echo "🚀 Starting Neo4j..."
docker exec "$CONTAINER_NAME" neo4j start

echo ""
echo "============================================================"
echo "✅ Load complete!"
echo "============================================================"

