#!/usr/bin/env bash
set -euo pipefail

# Configuration
export AZURE_OPENAI_API_KEY="${AZURE_OPENAI_API_KEY:-your-api-key-here}"
export AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:-https://your-resource-name.openai.azure.com}"
export AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2024-02-15-preview}"
MODEL="${MODEL:-gpt-5-nano}"
KNOWLEDGE_MODEL="${KNOWLEDGE_MODEL:-gpt-5-nano}"
WORKSPACE="./execution_agent_workspace"
MAX_RETRIES=2

# Check for metadata file argument
if [ $# -lt 1 ]; then
    echo "Usage: $0 <metadata-file.json> [additional-args...]"
    exit 1
fi

METADATA_FILE="$1"
shift  # Remove first argument, pass rest to the agent

python -m execution_agent.main \
    --experiment-file "$METADATA_FILE" \
    --model "$MODEL" \
    --knowledge-model "$KNOWLEDGE_MODEL" \
    --workspace-root "$WORKSPACE" \
    --max-retries "$MAX_RETRIES" \
    "$@"