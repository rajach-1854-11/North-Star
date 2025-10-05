# Table Dictionary

## abmap_edges

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| tenant_id | VARCHAR | No | No | No | Yes | - | - |
| from_project | VARCHAR | No | No | No | No | - | - |
| to_project | VARCHAR | No | No | No | No | - | - |
| topic | VARCHAR | No | No | No | No | - | - |
| weight | FLOAT | No | No | No | No | 0.0 | - |
| evidence_ids | JSON | No | No | No | No | [] | - |
| updated_at | DATETIME | No | No | No | No | UTC now | - |

**Indexes:**
- ix_abmap_edges_tenant_id
- idx_abmap_tenant_projects

## attribution_triage

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| provider | VARCHAR | No | No | No | No | - | - |
| delivery_key | VARCHAR | Yes | No | No | Yes | - | - |
| reason | VARCHAR | No | No | No | No | - | - |
| payload | JSON | No | No | No | No | {} | - |
| created_at | DATETIME | No | No | No | No | UTC now | - |
| processed_at | DATETIME | Yes | No | No | No | - | - |

**Indexes:**
- idx_triage_provider_delivery
- ix_attribution_triage_delivery_key

## audit_log

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| ts | DATETIME | No | No | No | No | UTC now | - |
| tenant_id | VARCHAR | No | No | No | Yes | - | - |
| actor_user_id | INTEGER | No | No | No | Yes | - | - |
| action | VARCHAR | No | No | No | No | - | - |
| args_hash | VARCHAR | No | No | No | No | - | - |
| result_code | INTEGER | No | No | No | No | - | - |
| request_id | VARCHAR | No | No | No | Yes | - | - |
| trace_id | VARCHAR | No | No | No | Yes | - | - |

**Indexes:**
- ix_audit_log_tenant_id
- ix_audit_log_trace_id
- ix_audit_log_request_id
- ix_audit_log_actor_user_id

## eval_run

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| dataset | VARCHAR | No | No | No | No | - | - |
| metrics | JSON | No | No | No | No | {} | - |
| created_at | DATETIME | No | No | No | No | UTC now | - |

## event

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| tenant_id | VARCHAR | No | No | No | Yes | - | - |
| project_id | INTEGER | No | No | No | Yes | - | - |
| developer_id | INTEGER | No | No | No | Yes | - | - |
| type | VARCHAR | No | No | No | No | - | - |
| payload_json | JSON | No | No | No | No | - | - |
| ts | DATETIME | No | No | No | No | UTC now | - |

**Indexes:**
- ix_event_tenant_id
- ix_event_developer_id
- ix_event_project_id

## integration_event_log

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| provider | VARCHAR | No | No | No | No | - | - |
| delivery_key | VARCHAR | No | No | No | No | - | - |
| action | VARCHAR | Yes | No | No | No | - | - |
| entity | VARCHAR | Yes | No | No | No | - | - |
| tenant_id | VARCHAR | Yes | No | No | No | - | - |
| processed_at | DATETIME | No | No | No | No | UTC now | - |
| status | VARCHAR | Yes | No | No | No | - | - |
| metadata | JSON | No | No | No | No | {} | - |

**Indexes:**
- idx_event_provider_delivery

**Unique Constraints:**
- uq_event_provider_delivery (provider, delivery_key)

## router_stats

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| tenant_id | VARCHAR | No | No | No | Yes | - | - |
| arm | VARCHAR | No | No | No | No | - | - |
| pulls | INTEGER | No | No | No | No | 0 | - |
| reward_sum | FLOAT | No | No | No | No | 0.0 | - |
| updated_at | DATETIME | No | No | No | No | UTC now | - |

**Indexes:**
- ix_router_stats_tenant_id

**Unique Constraints:**
- uq_router_stats_tenant_arm (tenant_id, arm)

## skill

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| name | VARCHAR | No | No | No | No | - | - |
| parent_id | INTEGER | Yes | No | No | No | - | skill.id |
| path_cache | VARCHAR | No | No | No | No | - | - |
| depth | INTEGER | No | No | No | No | 0 | - |

**Unique Constraints:**
- uq_skill_path (path_cache)

## tenant

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | VARCHAR | No | Yes | No | No | - | - |
| name | VARCHAR | No | No | No | No | - | - |

## tenant_mapper_weights

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| tenant_id | VARCHAR | No | No | Yes | No | - | - |
| weights | JSON | No | No | No | No | {} | - |
| updated_at | DATETIME | No | No | No | No | UTC now | - |

## project

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| key | VARCHAR | No | No | Yes | No | - | - |
| name | VARCHAR | No | No | No | No | - | - |
| description | TEXT | Yes | No | No | No | - | - |
| tenant_id | VARCHAR | No | No | No | No | - | tenant.id |

## user

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| username | VARCHAR | No | No | Yes | No | - | - |
| password_hash | VARCHAR | No | No | No | No | - | - |
| role | VARCHAR | No | No | No | No | - | - |
| tenant_id | VARCHAR | No | No | No | No | - | tenant.id |

## developer

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| user_id | INTEGER | No | No | Yes | No | - | user.id |
| display_name | VARCHAR | No | No | No | No | - | - |
| tenant_id | VARCHAR | No | No | No | No | - | tenant.id |

## project_skill

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| project_id | INTEGER | No | No | No | Yes | - | project.id |
| skill_id | INTEGER | No | No | No | Yes | - | skill.id |
| importance | FLOAT | No | No | No | No | 0.5 | - |
| last_updated_at | DATETIME | No | No | No | No | UTC now | - |

**Indexes:**
- ix_project_skill_skill_id
- ix_project_skill_project_id

**Unique Constraints:**
- uq_proj_skill (project_id, skill_id)

## repository_mapping

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| provider | VARCHAR | No | No | No | No | github | - |
| repo_full_name | VARCHAR | No | No | No | No | - | - |
| tenant_id | VARCHAR | No | No | No | Yes | - | tenant.id |
| project_id | INTEGER | Yes | No | No | Yes | - | project.id |
| metadata | JSON | No | No | No | No | {} | - |
| active | BOOLEAN | No | No | No | No | True | - |
| created_at | DATETIME | No | No | No | No | UTC now | - |
| updated_at | DATETIME | No | No | No | No | UTC now | - |

**Indexes:**
- idx_repo_provider_fullname
- ix_repository_mapping_project_id
- ix_repository_mapping_tenant_id

**Unique Constraints:**
- uq_repo_provider_fullname (provider, repo_full_name)

## tool_execution

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| ts | DATETIME | No | No | No | No | UTC now | - |
| tool | VARCHAR | No | No | No | No | - | - |
| actor_user_id | INTEGER | No | No | No | No | - | - |
| project_id | INTEGER | Yes | No | No | No | - | project.id |
| status | VARCHAR | No | No | No | No | - | - |
| request_id | VARCHAR | No | No | No | No | - | - |

## assignment

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| developer_id | INTEGER | No | No | No | Yes | - | developer.id |
| project_id | INTEGER | No | No | No | Yes | - | project.id |
| role | VARCHAR | Yes | No | No | No | - | - |
| start_date | DATE | Yes | No | No | No | - | - |
| end_date | DATE | Yes | No | No | No | - | - |
| status | VARCHAR | No | No | No | No | active | - |

**Indexes:**
- ix_assignment_project_id
- ix_assignment_developer_id

**Unique Constraints:**
- uq_dev_proj (developer_id, project_id)

## attribution_workflow

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| provider | VARCHAR | No | No | No | No | github | - |
| tenant_id | VARCHAR | No | No | No | Yes | - | tenant.id |
| project_id | INTEGER | Yes | No | No | Yes | - | project.id |
| repo_full_name | VARCHAR | No | No | No | No | - | - |
| pr_number | INTEGER | Yes | No | No | No | - | - |
| jira_key | VARCHAR | Yes | No | No | Yes | - | - |
| developer_id | INTEGER | Yes | No | No | Yes | - | developer.id |
| assertions | JSON | No | No | No | No | [] | - |
| pending_assertion_payload | JSON | No | No | No | No | {} | - |
| pr_created_at | DATETIME | Yes | No | No | No | - | - |
| pr_merged_at | DATETIME | Yes | No | No | No | - | - |
| jira_done_at | DATETIME | Yes | No | No | No | - | - |
| baseline_applied_at | DATETIME | Yes | No | No | No | - | - |
| baseline_delta | FLOAT | Yes | No | No | No | - | - |
| review_cycles | INTEGER | No | No | No | No | 0 | - |
| approvals_count | INTEGER | No | No | No | No | 0 | - |
| major_rework_requested | BOOLEAN | No | No | No | No | False | - |
| nit_comment_count | INTEGER | No | No | No | No | 0 | - |
| peer_review_credit | JSON | No | No | No | No | {} | - |
| time_to_merge_seconds | INTEGER | Yes | No | No | No | - | - |
| correlation_key | VARCHAR | Yes | No | No | Yes | - | - |
| last_payload_snapshot | JSON | No | No | No | No | {} | - |
| evidence | JSON | No | No | No | No | {} | - |
| created_at | DATETIME | No | No | No | No | UTC now | - |
| updated_at | DATETIME | No | No | No | No | UTC now | - |

**Indexes:**
- ix_attribution_workflow_jira_key
- ix_attribution_workflow_correlation_key
- idx_workflow_repo_pr
- ix_attribution_workflow_project_id
- ix_attribution_workflow_tenant_id
- ix_attribution_workflow_developer_id

**Unique Constraints:**
- uq_workflow_repo_pr (tenant_id, repo_full_name, pr_number)
- uq_workflow_jira (tenant_id, jira_key)

## developer_identity

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| developer_id | INTEGER | No | No | No | Yes | - | developer.id |
| tenant_id | VARCHAR | No | No | No | Yes | - | tenant.id |
| provider | VARCHAR | No | No | No | No | - | - |
| provider_login | VARCHAR | Yes | No | No | No | - | - |
| provider_user_id | VARCHAR | Yes | No | No | No | - | - |
| email | VARCHAR | Yes | No | No | No | - | - |
| email_lower | VARCHAR | Yes | No | No | Yes | - | - |
| is_primary | BOOLEAN | No | No | No | No | False | - |
| metadata | JSON | No | No | No | No | {} | - |
| created_at | DATETIME | No | No | No | No | UTC now | - |
| updated_at | DATETIME | No | No | No | No | UTC now | - |

**Indexes:**
- ix_developer_identity_email_lower
- idx_identity_provider_login
- ix_developer_identity_developer_id
- ix_developer_identity_tenant_id

**Unique Constraints:**
- uq_identity_provider_login (provider, provider_login)
- uq_identity_provider_user (provider, provider_user_id)
- uq_identity_provider_email (provider, email_lower)

## developer_skill

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| developer_id | INTEGER | No | No | No | Yes | - | developer.id |
| skill_id | INTEGER | No | No | No | Yes | - | skill.id |
| score | FLOAT | No | No | No | No | 0.0 | - |
| confidence | FLOAT | No | No | No | No | 0.5 | - |
| last_seen_at | DATETIME | No | No | No | No | UTC now | - |
| evidence_ref | VARCHAR | Yes | No | No | No | - | - |
| project_id | INTEGER | Yes | No | No | No | - | project.id |

**Indexes:**
- idx_devskill_dev_skill
- ix_developer_skill_developer_id
- ix_developer_skill_skill_id

**Unique Constraints:**
- uq_dev_skill (developer_id, skill_id)

## peer_review_credit

| Column | Type | Nullable | PK | Unique | Index | Default | Foreign Keys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| id | INTEGER | No | Yes | No | No | - | - |
| tenant_id | VARCHAR | No | No | No | Yes | - | tenant.id |
| reviewer_developer_id | INTEGER | No | No | No | Yes | - | developer.id |
| repo_full_name | VARCHAR | No | No | No | No | - | - |
| pr_number | INTEGER | No | No | No | No | - | - |
| credit_value | FLOAT | No | No | No | No | - | - |
| window_start | DATETIME | No | No | No | No | - | - |
| window_end | DATETIME | No | No | No | No | - | - |
| evidence | JSON | No | No | No | No | {} | - |
| created_at | DATETIME | No | No | No | No | UTC now | - |

**Indexes:**
- ix_peer_review_credit_tenant_id
- idx_peer_credit_window
- ix_peer_review_credit_reviewer_developer_id

**Unique Constraints:**
- uq_peer_credit_once_per_pr (tenant_id, reviewer_developer_id, repo_full_name, pr_number)

