#!/bin/bash
# Deactivate VVS and Reranking features for ADAM

echo "🔻 Deactivating ADAM features..."

# Disable VVS
unset VVS_ENABLED
unset VVS_INDEX
unset VVS_ENDPOINT
unset VVS_NAMESPACE_MODE
unset VVS_FORCE
unset VVS_MIN_FILES
unset VVS_MIN_CHUNKS
echo "✅ Disabled VVS"

# Disable Reranking
unset RERANK_ENABLED
unset RERANK_TOPK
echo "✅ Disabled reranking"

# Keep core settings
echo ""
echo "📊 Active Configuration:"
echo "  Project:      ${GOOGLE_CLOUD_PROJECT}"
echo "  Location:     ${GOOGLE_CLOUD_LOCATION}"
echo "  VVS:          disabled"
echo "  Reranking:    disabled"
echo ""
echo "✅ Features disabled. Running with base configuration only."