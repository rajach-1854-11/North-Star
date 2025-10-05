# Internal flow — `app.ports.retriever.rag_search`

- Module: `app.ports.retriever`
- Source: [app.ports.retriever.rag_search](../Src/backend/app/ports/retriever.py#L70)
- Summary: Execute the hybrid retriever and return fused payloads.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as rag_search
    Target->>Dependency: _assert_targets_allowed
    Target->>Dependency: _dedupe_by_chunk_id
    Target->>Dependency: _extract_plan_metadata
    Target->>Dependency: _meta_filters_from_plan
    Target->>Dependency: allowed_targets.add
    Target->>External: app.adapters.hybrid_retriever.search
    Target->>Dependency: app.application.contrastive_mapper.ABMapper
    Target->>Dependency: app.application.local_kb.search_chunks
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```