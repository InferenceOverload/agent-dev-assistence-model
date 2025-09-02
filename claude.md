You go read all the details about google ADK here:

https://google.github.io/adk-docs/ - Please read preffered sublinks as well. 

0) North-star: what we’re building

A multi-agent system on GCP (Vertex AI + Google ADK) with a chat UI that can:
	•	Ingest & understand arbitrary repos (React, Python, SQL, etc.), build a Code Map, answer questions, and generate living docs.
	•	Turn requirements → Rally stories/features/tasks.
	•	Implement a picked story, open a GitHub PR, and optionally spin up a sandbox to validate.
	•	Keep data session-scoped by default (no persistence unless explicitly enabled).

ADK gives you agents, tools, runners, sessions/memory, and deploy targets; it ships built-in tools (Google Search, Code Execution, Vertex AI Search, BigQuery) with important mixing limits.  ￼
Vertex AI provides Gemini models (incl. long-context) and Text Embeddings (e.g., gemini-embedding-001, 3072 dims, with configurable output_dimensionality).  ￼ ￼
Vertex Vector Search offers streaming upserts (indexes.upsertDatapoints) and partial updates.  ￼

⸻

1) Repository & ADK-friendly folder structure

Target tree (Claude Code will scaffold this in Phase A):

.
├─ README.md
├─ pyproject.toml | requirements.txt
├─ run_agent.py                     # local entry (adk web / adk api_server still used)
├─ src/
│  ├─ agents/
│  │  ├─ orchestrator.py
│  │  ├─ repo_ingestor.py
│  │  ├─ indexer.py
│  │  ├─ rag_answerer.py
│  │  ├─ planner_rally.py
│  │  ├─ dev_pr.py
│  │  └─ sandbox_runner.py
│  ├─ tools/
│  │  ├─ repo_io.py                 # clone, ls-tree, read files
│  │  ├─ parsing.py                 # tree-sitter/LSP (optional), language-aware splits
│  │  ├─ embeddings.py              # Vertex Text Embeddings API
│  │  ├─ vector_search.py           # Vertex Vector Search wrapper
│  │  ├─ retrieval.py               # BM25+vector hybrid, neighbor expansion
│  │  ├─ rally.py                   # Rally REST client
│  │  ├─ github.py                  # GitHub App/REST client
│  │  ├─ git_ops.py                 # branch/commit/diff helpers
│  │  ├─ code_exec.py               # ADK built-in code execution routing (separate agent)
│  │  └─ cloud_run.py               # sandbox deploy/teardown
│  ├─ services/
│  │  ├─ vertex_models.py           # model routing (Gemini variants)
│  │  └─ secrets.py                 # Secret Manager lookups
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ logging.py
│  │  └─ types.py                   # Pydantic models (Chunk, CodeMap, Story, PRPlan…)
│  └─ ui/
│     └─ fastapi_app.py             # optional chat UI proxy to ADK runner
├─ configs/
│  ├─ app.example.yaml
│  └─ prompts/                      # reusable prompt fragments
├─ docs/ (generated architecture/docs go here)
├─ infra/                           # Terraform / gcloud scripts (later)
├─ .github/workflows/               # CI
└─ tools/                           # maintenance scripts (cleanup, scan, bench)

ADK Runner & dev UI (“adk web”) run against your agents folder; deployment targets include Cloud Run.  ￼ ￼

⸻

2) Agent roster & how they talk

(A) Conversation Orchestrator (root agent)
	•	Model: gemini-2.0-flash (fast routing).
	•	Role: intent detect → call sub-agents as agents-as-tools (ADK pattern).
	•	Notes: Because ADK built-in tools (e.g., Google Search, Code Execution) have mixing limits, put those on dedicated sub-agents when needed.  ￼

(B) Repo Ingestor
	•	Model: Flash (tool-heavy).
	•	Tools: repo_io, parsing → emits Code Map (files, symbols, deps).

(C) Indexer
	•	Model: Flash.
	•	Tools: embeddings, vector_search. Builds in-session FAISS (optional) + Vertex Vector Search (streaming) when enabled. Upserts chunk vectors with metadata.  ￼

(D) RAG Answerer
	•	Model: gemini-1.5-pro (or 2.x long-context) for deep answers & repo docs. Uses retrieval tool → constructs sparse “doc packs” + dependency neighbors. Long-context best practices apply.  ￼

(E) Backlog Planner (Rally)
	•	Model: Flash (fast structured JSON).
	•	Tools: rally → create Feature/Story/Task via WS v2 (HierarchicalRequirement/create, task/create).  ￼ ￼

(F) Dev & PR Agent
	•	Model: gemini-1.5-pro for diff planning, Flash for quick edits.
	•	Tools: git_ops, github (PR create/update), retrieval (ground changes), call into a dedicated Code-Exec agent for tests (see G). GitHub PR endpoints used to open/update PRs.  ￼

(G) Code-Exec Agent (built-in tool)
	•	Model: Flash + Built-in Code Execution tool (Python) to run unit tests or small scripts. Must be isolated as its own agent due to built-in tool mixing limits.  ￼

(H) Sandbox Runner
	•	Model: Flash.
	•	Tools: cloud_run → build/deploy ephemeral preview; comment URL in PR.

Session & memory
	•	Runner: ADK Runner with InMemorySessionService for dev; for prod you can use VertexAiSessionService if you need managed sessions, but your requirement is session-only, so default in-memory with TTL. Memory Bank is optional/persistent (not default).  ￼ ￼

⸻

3) Model routing (what model where)
	•	Routing/Orchestrator: gemini-2.0-flash (speed).
	•	Repo Q&A & doc generation: gemini-1.5-pro (or long-context variant) when the assembled prompt > ~200–300k tokens; otherwise Flash works (faster).  ￼ ￼
	•	Embeddings: gemini-embedding-001 (default 3072-d, set output_dimensionality to 1536 for a good storage/quality tradeoff).  ￼ ￼
	•	Code execution: Built-in Code Execution tool (Gemini 2.x only). Place it on a dedicated agent.  ￼

⸻

4) Tools: built-in vs custom, and who uses what

Built-in ADK tools you can use today
	•	Google Search (if you ever need open-web grounding) — Gemini 2 only.
	•	Built-in Code Execution (Python snippets/tests).
	•	Vertex AI Search (if you attach Google’s Search datastore instead of your own RAG).
	•	BigQuery (data access).

Built-in constraints: one built-in tool per agent, and not inside sub-agents; use agents-as-tools to compose.  ￼

Custom tools to build (thin wrappers)
	•	repo_io (clone, read files, ls-tree)
	•	parsing (language-aware splitting via tree-sitter/LSP if desired)
	•	embeddings (Vertex Text Embeddings API client)  ￼
	•	vector_search (Vertex Vector Search: create/deploy index; streaming upserts with indexes.upsertDatapoints)  ￼
	•	retrieval (hybrid: BM25 + ANN; neighbor expansion via Code Map)
	•	rally (WS v2 endpoints or pyral)  ￼
	•	github (create branch/commit/PR; reviews; statuses)  ￼
	•	git_ops (local git actions or GitHub API contents endpoint)
	•	cloud_run (build/deploy/teardown; comment URL back to PR)  ￼

Attachment map (who calls what)
	•	Orchestrator → (Repo Ingestor, Indexer, RAG Answerer, Planner, Dev&PR, Sandbox) as tools.
	•	Repo Ingestor → repo_io, parsing.
	•	Indexer → embeddings, vector_search.
	•	RAG Answerer → retrieval (+ direct long-context when small).
	•	Planner → rally.
	•	Dev & PR → retrieval, git_ops, github, calls Code-Exec Agent for tests.
	•	Code-Exec Agent → Built-in Code Execution.
	•	Sandbox → cloud_run.

⸻

5) Vectorization & retrieval strategy (when/what to embed)

Chunking
	•	Prefer language-aware splits: function/class boundaries (tree-sitter) + import graph.
	•	Fallback: sliding windows of 200–400 LOC with ~50 LOC overlap; always store neighbors (parents/children in dep graph) in metadata.

Embeddings
	•	Model: gemini-embedding-001.
	•	Dimensionality: 1536 default (halve storage vs 3072; negligible quality loss for code search in practice).  ￼
	•	Metadata per chunk: {repo, commit, path, lang, symbols[], imports[], neighbors[], test_files[], hash}.

Index choices
	•	Default (session-only): In-RAM ANN (e.g., FAISS/HNSW) in the process (no persistence).
	•	Large repos or reuse: a Vertex Vector Search streaming index, created empty and deployed immediately, then upsert as you ingest; query is available as soon as the first upserts land.  ￼

Heuristics: when to embed vs rely on long context
	•	If repo <= ~80k LOC and your task scope is narrow → consider long-context only (no vectors) to simplify.
	•	80k–400k LOC → hybrid: embed code and build “doc packs” for long-context synthesis.
	•	>400k LOC or monorepos → embed. Use Vertex Vector Search if you need concurrent sessions or reuse; otherwise in-memory ANN per session is fine.

Long-context models support ~1M–2M tokens; still, retrieval beats dumping the world into the prompt. Use sparse context packs (top-k + neighbors) for reasoning.  ￼ ￼

Retrieval
	•	Hybrid ranking: lexical (BM25 over path/symbol text) + ANN cosine, re-rank by path similarity + neighbor boost + test proximity.
	•	Pack assembly: top-k chunks plus immediate neighbors (deps/tests) to keep cross-file logic intact.

⸻

6) Runners, sessions & memory
	•	Use ADK Runner with InMemorySessionService by default (RAM, ephemeral).  ￼
	•	For managed sessions (if needed later), swap to VertexAiSessionService; for persistent Memory Bank, ADK has VertexAiMemoryBankService (you said avoid persistence by default).  ￼ ￼
	•	Enforce TTL at app layer (expire session + drop ANN index) to honor session-only policy.

⸻

7) Rally & GitHub specifics
	•	Rally: Use WS v2 REST (HierarchicalRequirement/create, task/create…), or pyral Python SDK. Link each work item to code paths and acceptance tests.  ￼ ￼
	•	GitHub: Branch → commits → Create PR → post diffs, test results, sandbox URL. Use REST pulls API.  ￼

⸻

8) Deployment & observability
	•	Dev: adk web for the interactive dev UI; adk api_server for local API.  ￼
	•	Prod: Cloud Run via adk deploy cloud_run or gcloud run deploy. Add logging/tracing exporters.  ￼

⸻

9) The work plan (paste-ready tasks for Claude Code)

Below are sequenced packs. Paste each prompt; Claude will create files and stubs without breaking anything. You can run commits between packs.

⸻

Phase A — Bootstrap & structure

Prompt A1 (scaffold)

Create the folder tree described below if missing. Do not overwrite existing files. Add placeholder README.md in empty dirs.

Paths:
src/agents/{orchestrator.py,repo_ingestor.py,indexer.py,rag_answerer.py,planner_rally.py,dev_pr.py,sandbox_runner.py}
src/tools/{repo_io.py,parsing.py,embeddings.py,vector_search.py,retrieval.py,rally.py,github.py,git_ops.py,code_exec.py,cloud_run.py}
src/services/{vertex_models.py,secrets.py}
src/core/{config.py,logging.py,types.py}
src/ui/{fastapi_app.py}
configs/prompts/
docs/
tools/
.github/workflows/

Prompt A2 (deps & config)

Create pyproject.toml (or update requirements.txt) with pinned deps:
- google-cloud-aiplatform[vertex_sdk,vector-search] ~= 1.71
- vertexai ~= 1.71
- pydantic ~= 2.8
- httpx ~= 0.27
- gitpython ~= 3.1
- pyyaml ~= 6.0
- redis ~= 5.0
- uvicorn ~= 0.30
- fastapi ~= 0.111
- whoosh ~= 2.7  # lightweight BM25 (or use rank_bm25)
- rank-bm25 ~= 0.2
- (optional) faiss-cpu ~= 1.8  # comment out by default

Dev:
- ruff ~= 0.5, mypy ~= 1.10, pytest ~= 8.3

Generate configs/app.example.yaml with placeholders for:
GCP project/location, Vertex models, Rally creds, GitHub app creds, sandbox GCR repo, session TTL minutes.

Prompt A3 (runner & UI)

Add run_agent.py that starts:
- ADK Runner with InMemorySessionService
- loads root Orchestrator agent
Add src/ui/fastapi_app.py with a minimal /chat endpoint that forwards to Runner.run_async.
Add .github/workflows/lint.yml running ruff + mypy on src/.


⸻

Phase B — Core types, logging, and model router

Prompt B1 (types & config)

In src/core/types.py create Pydantic models:
- Chunk {id, repo, commit, path, lang, start_line, end_line, text, symbols: list[str], imports: list[str], neighbors: list[str], hash}
- CodeMap {repo, commit, files: list[str], deps: dict[str, list[str]], symbol_index: dict[str, list[str]]}
- RetrievalResult {chunk_id, path, score, neighbors: list[str]}
- StorySpec {title, description, acceptance_criteria: list[str], impacted_paths: list[str]}
- PRPlan {branch, commits: list[str], summary, impacted_paths: list[str], tests: list[str]}

In src/core/config.py load configs/app.yaml with env overrides.
In src/core/logging.py set structured logging and redaction helpers.

Prompt B2 (model router)

In src/services/vertex_models.py add a ModelRouter with:
- llm_fast(): gemini-2.0-flash
- llm_deep(): gemini-1.5-pro (or long-context)
- embedder(dim=1536): gemini-embedding-001 with output_dimensionality
Expose simple functions to call Vertex AI via google-cloud-aiplatform / vertexai SDKs.

(References: Gemini long-context and embeddings dimensionality).  ￼ ￼

⸻

Phase C — Repo ingestion & parsing

Prompt C1 (repo IO)

In src/tools/repo_io.py implement:
- clone_repo(url, ref) -> local_path
- list_files(local_path, include_globs, exclude_globs) -> list[str]
- read_file(local_path, path) -> str
Ensure safe path handling & size limits.

Prompt C2 (parsing & chunking)

In src/tools/parsing.py implement:
- detect_language(path) -> str
- split_code(text, lang) -> list[(start_line, end_line, text)]
  Strategy: try function/class boundaries (if tree-sitter present); else sliding windows of 200–400 LOC with 50 overlap.
- build_code_map(files, read_fn) -> CodeMap with deps (from imports) and symbol index (regex fallback).
Add unit tests for Python and JS files.


⸻

Phase D — Embeddings & Vector Search

Prompt D1 (embeddings client)

In src/tools/embeddings.py implement get_embeddings(texts: list[str], dim=1536) -> list[list[float]] using gemini-embedding-001 with output_dimensionality.
Batch size 1–8, retry with jitter on 429/5xx.

(Embeddings capacity & dims).  ￼ ￼

Prompt D2 (Vertex Vector Search wrapper)

In src/tools/vector_search.py implement:
- ensure_streaming_index(name, dims) -> {index_name, endpoint}
- upsert(chunks: list[Chunk], vectors: list[list[float]]) -> UpsertStats
- query(vector, k, filter=None) -> list[RetrievalResult]
Use REST projects.locations.indexes.upsertDatapoints endpoint.

(Upsert API & updates).  ￼

Prompt D3 (Indexer agent)

In src/agents/indexer.py implement an ADK agent that:
- receives CodeMap + file iterator
- yields Chunk objects
- calls embeddings.get_embeddings on chunk texts
- if config.vector.enabled: calls vector_search.ensure_streaming_index + upsert
- else: stores vectors in an in-memory ANN (guarded by feature flag)


⸻

Phase E — Retrieval & RAG Answerer

Prompt E1 (hybrid retrieval)

In src/tools/retrieval.py implement:
- bm25_index(chunks) using rank_bm25 or whoosh
- ann_index(vectors) with FAISS (if installed) else cosine over Python lists for k<=50
- search(query_text, k=12) -> list[RetrievalResult]
  Steps: embed query; get ANN candidates; get BM25 candidates; merge via reciprocal rank fusion; expand with neighbor chunks from CodeMap; return scored results.

Prompt E2 (RAG Answerer agent)

In src/agents/rag_answerer.py implement:
- assemble a "doc pack": top-k chunks (+ neighbors) with headers {path, symbols, imports}
- choose model: deep() if total tokens > 200k else fast()
- produce: short answer + sources; optional docs into docs/ generated markdown

(Long-context patterns).  ￼

⸻

Phase F — Rally planner

Prompt F1 (Rally client & agent)

In src/tools/rally.py implement create_feature, create_story, create_task using Rally Web Services v2 endpoints, or pyral if available.
In src/agents/planner_rally.py implement:
- input: free-form requirement + impacted_paths
- output: StorySpec[] with ACs; then call rally.create_* to persist and return links/ids

(Rally API/pyral).  ￼ ￼

⸻

Phase G — Dev & PR flow + Code Execution agent

Prompt G1 (GitHub client & git ops)

In src/tools/github.py implement:
- create_branch(repo, from_sha, new_branch)
- commit_files(repo, branch, {path->content}, message)
- create_pull_request(repo, head, base, title, body) -> url
Reference GitHub REST v3 pulls API.
In src/tools/git_ops.py implement local diffs and patch application helpers.

(GitHub PR API).  ￼

Prompt G2 (Code-Exec agent)

Create src/agents/code_exec_agent.py that uses ADK Built-in Code Execution:
- dedicated agent with code_executor=BuiltInCodeExecutor()
- tool: run_pytest(path, markers=None) -> parse results and return summary

(Built-in code execution tool usage & limits).  ￼

Prompt G3 (Dev & PR agent)

In src/agents/dev_pr.py implement:
- plan edits based on StorySpec + retrieval context
- generate diffs; apply changes with git_ops
- call Code-Exec agent to run tests; collect results
- open a draft PR via github.create_pull_request, include summary + test output


⸻

Phase H — Sandbox (Cloud Run)

Prompt H1 (sandbox tool & agent)

In src/tools/cloud_run.py implement:
- build_and_deploy(container_name, source_dir, env) -> url
- teardown(container_name)
In src/agents/sandbox_runner.py implement:
- on request: build & deploy preview; comment PR with URL

(Cloud Run deploy with ADK docs as reference).  ￼

⸻

Phase I — Orchestrator & wiring

Prompt I1 (orchestrator)

In src/agents/orchestrator.py implement a root ADK agent:
- model: gemini-2.0-flash
- intent router: {ingest, ask, plan, dev, sandbox}
- sub-agents as tools: RepoIngestor, Indexer, RAG Answerer, Planner, DevPR, Sandbox
- separate sub-agent for built-in Code Exec (do not mix in others)
Return structured responses with references to chunk paths/ids.

(Agents-as-tools composition and built-in tool separation).  ￼

⸻

Phase J — Security, sessions & ops

Prompt J1 (sessions & TTL)

Wire ADK Runner with InMemorySessionService; add TTL eviction in app layer.
Ensure any in-memory ANN indices and temp clones are cleaned on session end.
Expose /healthz, /metrics (optional).

(ADK runner & sessions).  ￼

Prompt J2 (observability)

Add Cloud Logging & Trace exporters. Structure logs: {agent, tool, user_id, session_id, event_id}. Redact secrets by key name.

Prompt J3 (CI)

Update GitHub Actions:
- lint/typecheck
- unit tests for parsing & retrieval
- a "smoke" flow: ingest tiny sample repo, answer 1 Q, plan 1 story (mock Rally/GitHub).


⸻

10) Operational guidance (rules of thumb)
	•	When to embed: above (~80k LOC) or whenever users hop around multiple modules. For small, localized questions, try long-context only to reduce latency/cost. (Gemini long-context can go to 1–2M tokens, but retrieval still wins for latency & grounding.)  ￼ ￼
	•	Embedding dims: 1536 default; use 3072 only if you notice recall gaps; 768 for super-tight latency/storage.  ￼
	•	Vector Search: prefer streaming index → deploy immediately → upsertDatapoints while ingesting; you can query as soon as first upserts land.  ￼
	•	Built-in tools: don’t mix with other tools on the same agent; mount them as dedicated agents and call them from the orchestrator.  ￼
	•	Sessions: default InMemorySessionService (ephemeral) to meet your “session-only” policy; Memory Bank is available if you later choose persistence.  ￼

⸻

If you want, I can tweak any part of this plan for your company’s standards (naming, CI platform, Terraform layout). Otherwise, start with Phase A and push through the phases — the prompts are designed so you can paste them one-by-one into Claude Code and keep commits tight.