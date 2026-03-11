#!/usr/bin/env bash
set -euo pipefail

export AZURE_OPENAI_API_KEY="${AZURE_OPENAI_API_KEY:-your-api-key-here}"
export AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:-https://your-resource-name.openai.azure.com}"
export AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2024-02-15-preview}"

# Model presets
case "${1:-}" in
    "fast")
        MODEL="gpt-5-nano"
        KNOWLEDGE_MODEL="gpt-5-nano"
        ;;
    "balanced")
        MODEL="gpt-5-nano"
        KNOWLEDGE_MODEL="gpt-5-nano"
        ;;
    "quality")
        MODEL="gpt-5-nano"
        KNOWLEDGE_MODEL="gpt-5-nano"
        ;;
    "claude")
        MODEL="claude-sonnet-4-20250514"
        KNOWLEDGE_MODEL="claude-sonnet-4-20250514"
        ;;
    *)
        echo "Usage: $0 <fast|balanced|quality|claude> <metadata-file.json>"
        exit 1
        ;;
esac

METADATA_FILE="${2:-}"
if [ -z "$METADATA_FILE" ]; then
    echo "Usage: $0 <fast|balanced|quality|claude> <metadata-file.json>"
    exit 1
fi

echo "Running with MODEL=$MODEL, KNOWLEDGE_MODEL=$KNOWLEDGE_MODEL"

python -m execution_agent.main \
    --experiment-file "$METADATA_FILE" \
    --model "$MODEL" \
    --knowledge-model "$KNOWLEDGE_MODEL" \
    --workspace-root "./execution_agent_workspace" \
    --max-retries 2