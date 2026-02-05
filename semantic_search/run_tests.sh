#!/bin/bash
# Script to run all tests for the semantic search system

set -e

echo "🧪 Running API tests..."
cd api && python -m pytest tests/ -v

echo ""
echo "🧪 Running Ingest tests..."
cd ../ingest && python -m pytest tests/ -v

echo ""
echo "✅ All tests completed!"
