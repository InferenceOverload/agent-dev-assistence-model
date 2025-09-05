#!/bin/bash
# Activate VVS and Reranking features for ADAM

echo "🚀 Activating ADAM features..."

# Load VVS configuration
if [ -f .env.vvs ]; then
    set -a
    source .env.vvs
    set +a
    echo "✅ Loaded VVS configuration"
else
    echo "❌ Warning: .env.vvs not found. Run 'make vvs-setup' first."
fi

# Enable Reranking
export RERANK_ENABLED=1
export RERANK_TOPK=80
echo "✅ Enabled LLM reranking (top-80)"

# Force VVS for testing (even on small repos)
export VVS_FORCE=1
export VVS_MIN_FILES=50
export VVS_MIN_CHUNKS=500
echo "✅ Forced VVS with lowered thresholds for testing"

# Set Python path
export PYTHONPATH="$(pwd)"
echo "✅ Set PYTHONPATH"

# Display active configuration
echo ""
echo "📊 Active Configuration:"
echo "  Project:      ${GOOGLE_CLOUD_PROJECT}"
echo "  Location:     ${GOOGLE_CLOUD_LOCATION}"
echo "  VVS Enabled:  ${VVS_ENABLED}"
echo "  VVS Index:    ${VVS_INDEX##*/}"  # Show just the ID
echo "  VVS Endpoint: ${VVS_ENDPOINT##*/}"  # Show just the ID
echo "  VVS Force:    ${VVS_FORCE}"
echo "  Reranking:    ${RERANK_ENABLED}"
echo "  Rerank TopK:  ${RERANK_TOPK}"
echo ""
echo "🎯 Ready! Run 'adk web' to start with all features enabled."
echo "💡 Tip: Run 'deactivate_features.sh' to disable features."