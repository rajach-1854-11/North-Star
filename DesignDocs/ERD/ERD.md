```mermaid
erDiagram
    ABMAP_EDGES {
        INTEGER id PK
        VARCHAR tenant_id 
        VARCHAR from_project 
        VARCHAR to_project 
        VARCHAR topic 
        FLOAT weight default 0.0
        JSON evidence_ids default <function list at 0x000001D8A905D260>
        DATETIME updated_at default <function _utc_now at 0x000001D8A905D300>
    }
    ATTRIBUTION_TRIAGE {
        INTEGER id PK
        VARCHAR provider 
        VARCHAR delivery_key NULL
        VARCHAR reason 
        JSON payload default <function dict at 0x000001D8A8FFF920>
        DATETIME created_at default <function _utc_now at 0x000001D8A8FFF9C0>
        DATETIME processed_at NULL
    }
    AUDIT_LOG {
        INTEGER id PK
        DATETIME ts default <function _utc_now at 0x000001D8A902C900>
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
        JSON metrics default <function dict at 0x000001D8A905E200>
        DATETIME created_at default <function _utc_now at 0x000001D8A905E2A0>
    }
    EVENT {
        INTEGER id PK
        VARCHAR tenant_id 
        INTEGER project_id 
        INTEGER developer_id 
        VARCHAR type 
        JSON payload_json 
        DATETIME ts default <function _utc_now at 0x000001D8A902D940>
    }
    INTEGRATION_EVENT_LOG {
        INTEGER id PK
        VARCHAR provider 
        VARCHAR delivery_key 
        VARCHAR action NULL
        VARCHAR entity NULL
        VARCHAR tenant_id NULL
        DATETIME processed_at default <function _utc_now at 0x000001D8A8FD63E0>
        VARCHAR status NULL
        JSON metadata default <function dict at 0x000001D8A8FD6480>
    }
    ROUTER_STATS {
        INTEGER id PK
        VARCHAR tenant_id 
        VARCHAR arm 
        INTEGER pulls default 0
        FLOAT reward_sum default 0.0
        DATETIME updated_at default <function _utc_now at 0x000001D8A902F6A0>
    }
    SKILL {
        INTEGER id PK
        VARCHAR name 
        INTEGER parent_id NULL
        VARCHAR path_cache 
        INTEGER depth default 0
    }
    TENANT {
        VARCHAR id PK
        VARCHAR name 
    }
    TENANT_MAPPER_WEIGHTS {
        INTEGER id PK
        VARCHAR tenant_id UQ
        JSON weights default <function dict at 0x000001D8A905C4A0>
        DATETIME updated_at default <function _utc_now at 0x000001D8A905C540>
    }
    PROJECT {
        INTEGER id PK
        VARCHAR key UQ
        VARCHAR name 
        TEXT description NULL
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
        FLOAT importance default 0.5
        DATETIME last_updated_at default <function _utc_now at 0x000001D8A8F6BD80>
    }
    REPOSITORY_MAPPING {
        INTEGER id PK
        VARCHAR provider default github
        VARCHAR repo_full_name 
        VARCHAR tenant_id 
        INTEGER project_id NULL
        JSON metadata default <function dict at 0x000001D8A8FD4A40>
        BOOLEAN active default True
        DATETIME created_at default <function _utc_now at 0x000001D8A8FD4F40>
        DATETIME updated_at default <function _utc_now at 0x000001D8A8FD5080>
    }
    TOOL_EXECUTION {
        INTEGER id PK
        DATETIME ts default <function _utc_now at 0x000001D8A902E7A0>
        VARCHAR tool 
        INTEGER actor_user_id 
        INTEGER project_id NULL
        VARCHAR status 
        VARCHAR request_id 
    }
    ASSIGNMENT {
        INTEGER id PK
        INTEGER developer_id 
        INTEGER project_id 
        VARCHAR role NULL
        DATE start_date NULL
        DATE end_date NULL
        VARCHAR status default active
    }
    ATTRIBUTION_WORKFLOW {
        INTEGER id PK
        VARCHAR provider default github
        VARCHAR tenant_id 
        INTEGER project_id NULL
        VARCHAR repo_full_name 
        INTEGER pr_number NULL
        VARCHAR jira_key NULL
        INTEGER developer_id NULL
        JSON assertions default <function list at 0x000001D8A8FD77E0>
        JSON pending_assertion_payload default <function dict at 0x000001D8A8FD7920>
        DATETIME pr_created_at NULL
        DATETIME pr_merged_at NULL
        DATETIME jira_done_at NULL
        DATETIME baseline_applied_at NULL
        FLOAT baseline_delta NULL
        INTEGER review_cycles default 0
        INTEGER approvals_count default 0
        BOOLEAN major_rework_requested default False
        INTEGER nit_comment_count default 0
        JSON peer_review_credit default <function dict at 0x000001D8A8FD7BA0>
        INTEGER time_to_merge_seconds NULL
        VARCHAR correlation_key NULL
        JSON last_payload_snapshot default <function dict at 0x000001D8A8FD7C40>
        JSON evidence default <function dict at 0x000001D8A8FD7CE0>
        DATETIME created_at default <function _utc_now at 0x000001D8A8FD7D80>
        DATETIME updated_at default <function _utc_now at 0x000001D8A8FD7E20>
    }
    DEVELOPER_IDENTITY {
        INTEGER id PK
        INTEGER developer_id 
        VARCHAR tenant_id 
        VARCHAR provider 
        VARCHAR provider_login NULL
        VARCHAR provider_user_id NULL
        VARCHAR email NULL
        VARCHAR email_lower NULL
        BOOLEAN is_primary default False
        JSON metadata default <function dict at 0x000001D8A8FA72E0>
        DATETIME created_at default <function _utc_now at 0x000001D8A8FA7380>
        DATETIME updated_at default <function _utc_now at 0x000001D8A8FA7420>
    }
    DEVELOPER_SKILL {
        INTEGER id PK
        INTEGER developer_id 
        INTEGER skill_id 
        FLOAT score default 0.0
        FLOAT confidence default 0.5
        DATETIME last_seen_at default <function _utc_now at 0x000001D8A8FA4EA0>
        VARCHAR evidence_ref NULL
        INTEGER project_id NULL
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
        JSON evidence default <function dict at 0x000001D8A8FFE020>
        DATETIME created_at default <function _utc_now at 0x000001D8A8FFE340>
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
