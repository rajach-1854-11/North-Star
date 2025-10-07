```mermaid
erDiagram
    ABMAP_EDGES {
        INTEGER id PK
        VARCHAR tenant_id
        VARCHAR from_project
        VARCHAR to_project
        VARCHAR topic
        FLOAT weight
        JSON evidence_ids
        DATETIME updated_at
    }
    ATTRIBUTION_TRIAGE {
        INTEGER id PK
        VARCHAR provider
        VARCHAR delivery_key
        VARCHAR reason
        JSON payload
        DATETIME created_at
        DATETIME processed_at
    }
    AUDIT_LOG {
        INTEGER id PK
        DATETIME ts
        VARCHAR tenant_id
        INTEGER actor_user_id
        VARCHAR action
        VARCHAR args_hash
        INTEGER result_code
        VARCHAR request_id
        VARCHAR trace_id
    }
    EVAL_RUN {
        INTEGER id PK
        VARCHAR dataset
        JSON metrics
        DATETIME created_at
    }
    EVENT {
        INTEGER id PK
        VARCHAR tenant_id
        INTEGER project_id
        INTEGER developer_id
        VARCHAR type
        JSON payload_json
        DATETIME ts
    }
    INTEGRATION_EVENT_LOG {
        INTEGER id PK
        VARCHAR provider
        VARCHAR delivery_key
        VARCHAR action
        VARCHAR entity
        VARCHAR tenant_id
        DATETIME processed_at
        VARCHAR status
        JSON metadata
    }
    ROUTER_STATS {
        INTEGER id PK
        VARCHAR tenant_id
        VARCHAR arm
        INTEGER pulls
        FLOAT reward_sum
        DATETIME updated_at
    }
    SKILL {
        INTEGER id PK
        VARCHAR name
        INTEGER parent_id
        VARCHAR path_cache
        INTEGER depth
    }
    TENANT {
        VARCHAR id PK
        VARCHAR name
    }
    TENANT_MAPPER_WEIGHTS {
        INTEGER id PK
        VARCHAR tenant_id UQ
        JSON weights
        DATETIME updated_at
    }
    PROJECT {
        INTEGER id PK
        VARCHAR key UQ
        VARCHAR name
        TEXT description
        VARCHAR tenant_id
    }
    USER {
        INTEGER id PK
        VARCHAR username UQ
        VARCHAR password_hash
        VARCHAR role
        VARCHAR tenant_id
    }
    DEVELOPER {
        INTEGER id PK
        INTEGER user_id UQ
        VARCHAR display_name
        VARCHAR tenant_id
    }
    PROJECT_SKILL {
        INTEGER id PK
        INTEGER project_id
        INTEGER skill_id
        FLOAT importance
        DATETIME last_updated_at
    }
    REPOSITORY_MAPPING {
        INTEGER id PK
        VARCHAR provider
        VARCHAR repo_full_name
        VARCHAR tenant_id
        INTEGER project_id
        JSON metadata
        BOOLEAN active
        DATETIME created_at
        DATETIME updated_at
    }
    TOOL_EXECUTION {
        INTEGER id PK
        DATETIME ts
        VARCHAR tool
        INTEGER actor_user_id
        INTEGER project_id
        VARCHAR status
        VARCHAR request_id
    }
    ASSIGNMENT {
        INTEGER id PK
        INTEGER developer_id
        INTEGER project_id
        VARCHAR role
        DATE start_date
        DATE end_date
        VARCHAR status
    }
    ATTRIBUTION_WORKFLOW {
        INTEGER id PK
        VARCHAR provider
        VARCHAR tenant_id
        INTEGER project_id
        VARCHAR repo_full_name
        INTEGER pr_number
        VARCHAR jira_key
        INTEGER developer_id
        JSON assertions
        JSON pending_assertion_payload
        DATETIME pr_created_at
        DATETIME pr_merged_at
        DATETIME jira_done_at
        DATETIME baseline_applied_at
        FLOAT baseline_delta
        INTEGER review_cycles
        INTEGER approvals_count
        BOOLEAN major_rework_requested
        INTEGER nit_comment_count
        JSON peer_review_credit
        INTEGER time_to_merge_seconds
        VARCHAR correlation_key
        JSON last_payload_snapshot
        JSON evidence
        DATETIME created_at
        DATETIME updated_at
    }
    DEVELOPER_IDENTITY {
        INTEGER id PK
        INTEGER developer_id
        VARCHAR tenant_id
        VARCHAR provider
        VARCHAR provider_login
        VARCHAR provider_user_id
        VARCHAR email
        VARCHAR email_lower
        BOOLEAN is_primary
        JSON metadata
        DATETIME created_at
        DATETIME updated_at
    }
    DEVELOPER_SKILL {
        INTEGER id PK
        INTEGER developer_id
        INTEGER skill_id
        FLOAT score
        FLOAT confidence
        DATETIME last_seen_at
        VARCHAR evidence_ref
        INTEGER project_id
    }
    PEER_REVIEW_CREDIT {
        INTEGER id PK
        VARCHAR tenant_id
        INTEGER reviewer_developer_id
        VARCHAR repo_full_name
        INTEGER pr_number
        FLOAT credit_value
        DATETIME window_start
        DATETIME window_end
        JSON evidence
        DATETIME created_at
    }
    SKILL ||--o{ SKILL : "parent_id"
    PROJECT ||--o{ TENANT : "tenant_id"
    USER ||--o{ TENANT : "tenant_id"
    DEVELOPER ||--o{ USER : "user_id"
    DEVELOPER ||--o{ TENANT : "tenant_id"
    PROJECT_SKILL ||--o{ PROJECT : "project_id"
    PROJECT_SKILL ||--o{ SKILL : "skill_id"
    REPOSITORY_MAPPING ||--o{ TENANT : "tenant_id"
    REPOSITORY_MAPPING ||--o{ PROJECT : "project_id"
    TOOL_EXECUTION ||--o{ PROJECT : "project_id"
    ASSIGNMENT ||--o{ DEVELOPER : "developer_id"
    ASSIGNMENT ||--o{ PROJECT : "project_id"
    ATTRIBUTION_WORKFLOW ||--o{ TENANT : "tenant_id"
    ATTRIBUTION_WORKFLOW ||--o{ PROJECT : "project_id"
    ATTRIBUTION_WORKFLOW ||--o{ DEVELOPER : "developer_id"
    DEVELOPER_IDENTITY ||--o{ DEVELOPER : "developer_id"
    DEVELOPER_IDENTITY ||--o{ TENANT : "tenant_id"
    DEVELOPER_SKILL ||--o{ DEVELOPER : "developer_id"
    DEVELOPER_SKILL ||--o{ SKILL : "skill_id"
    DEVELOPER_SKILL ||--o{ PROJECT : "project_id"
    PEER_REVIEW_CREDIT ||--o{ TENANT : "tenant_id"
    PEER_REVIEW_CREDIT ||--o{ DEVELOPER : "reviewer_developer_id"
```

### Notes
- Relationships default to one-to-many; adjust manually if needed.
