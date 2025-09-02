Run this end-to-end workflow.
Inputs:
- Query: $1
- Requirement: $2  (optional; if empty, skip planning/dev/sandbox)

Steps:
1) /size
2) /decide
3) /ingest
4) /index
5) /search "$1"
6) /rag "$1"
7) If "$2" not empty:
   - /plan "$2"
   - /dev
   - /sandbox