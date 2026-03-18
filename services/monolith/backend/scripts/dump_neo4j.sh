#!/bin/bash
# Export Neo4j database to dump file

set -e

DUMP_DIR="../dumps/neo4j"
CONTAINER_NAME="finance-neo4j"

echo "============================================================"
echo "📦 Neo4j Dump Script"
echo "============================================================"

# Create dump directory
mkdir -p "$DUMP_DIR"

# Check if container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Container '$CONTAINER_NAME' is not running!"
    echo "   Start it with: docker-compose up -d neo4j"
    exit 1
fi

echo "✅ Container '$CONTAINER_NAME' is running"

# Stop Neo4j (required for dump)
echo "🛑 Stopping Neo4j..."
docker exec "$CONTAINER_NAME" neo4j stop || true

# Wait a moment
sleep 2

# Create dump
echo "📦 Creating dump..."
docker exec "$CONTAINER_NAME" neo4j-admin database dump neo4j \
    --to-path=/dumps \
    --overwrite-destination=true

# Copy dump to host
echo "📋 Copying dump to host..."
docker cp "$CONTAINER_NAME:/dumps/neo4j.dump" "$DUMP_DIR/neo4j.dump"

# Start Neo4j again
echo "🚀 Starting Neo4j..."
docker exec "$CONTAINER_NAME" neo4j start

echo ""
echo "============================================================"
echo "✅ Dump complete!"
echo "📁 Dump saved to: $DUMP_DIR/neo4j.dump"
echo "============================================================"

