---
name: build-rag
description: Build RAG components (embeddings, retrieval, answerer)
---
Build the RAG system components by running the subagents in sequence:

1. First, run the embeddings subagent to create src/tools/embeddings.py
2. Then run the retriever subagent to create src/tools/retrieval.py  
3. Finally run the rag-answerer subagent to create src/agents/rag_answerer.py
4. Execute all tests and show a summary

This command will:
- Generate production-ready code for text embeddings using Vertex AI
- Create a hybrid retrieval system with BM25 and vector search
- Build the RAG answering agent with context assembly
- Run all tests to ensure correctness

Usage: /build-rag