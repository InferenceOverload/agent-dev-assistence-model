---
name: policy-decider
description: |
  IMPLEMENT CODE: Create a deterministic vectorization policy with tests.

  Deliverables:
  1) src/core/policy.py:
     - Pydantic:
         class VectorizationDecision(BaseModel):
             use_embeddings: bool
             backend: str            # "in_memory" | "vertex_vector_search"
             reasons: list[str]
     - def decide_vectorization(s: "SizerReport",
                                expected_concurrent_sessions: int = 1,
                                reuse_repo_across_sessions: bool = False) -> VectorizationDecision:
         """
         Rules:
         A) use_embeddings = True if ANY:
              s.loc_total>=80_000 or s.file_count>=1_500 or
              s.vector_count_estimate>=8_000 or s.estimated_tokens_repo>=1_500_000
         B) backend = "in_memory" unless ANY:
              s.vector_count_estimate>=50_000 or s.bytes_total>=1_500_000_000 or
              (expected_concurrent_sessions>=3 and s.vector_count_estimate>=20_000) or
              reuse_repo_across_sessions
         Append 1-line reasons for each fired rule.
         """

  2) tests/test_policy.py:
     - Build small SizerReport-like fixtures (you can define a minimal class or re-use from tools.sizer).
     - Each rule flips correctly; reasons include a human-readable line.

  3) Packaging:
     - Ensure imports resolve (policy imports SizerReport by dotted path or via typing.ForwardRef).

  Process:
  - Show diffs.
  - Run pytest -q.
  - Commit: "feat(core): vectorization policy + tests"
tools: Read, Write, Edit, Bash
---