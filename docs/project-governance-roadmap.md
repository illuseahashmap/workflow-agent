# Project Governance and Roadmap

Last updated: 2026-08-03

## Purpose

This document is the cross-repository engineering contract for Workflow Agent. It records the risks that remain after the current workflow-platform baseline and defines the order in which the platform must evolve before implementing a production Agent Runtime.

The project is currently suitable for internal evaluation and controlled pilots. It is not yet presented as a production-ready public multi-tenant SaaS. New capabilities must preserve security, tenancy, auditability, recoverability, and repository release boundaries.

Detailed repository rules:

- [Backend governance and roadmap](https://github.com/illuseahashmap/workflow-agent-service/blob/init/docs/quality/architecture-governance-and-roadmap.md)
- [Frontend governance and roadmap](https://github.com/illuseahashmap/workflow-agent-web/blob/init/docs/quality/frontend-governance-and-roadmap.md)

## Non-negotiable boundaries

1. BPMN owns durable business state. An agent may execute a governed step but must not become an untracked source of workflow truth.
2. Every business operation, cache entry, lock, background command, audit record, and Flowable query must have an explicit trusted tenant scope.
3. Browser clients never receive service-client secrets, model-provider secrets, or unrestricted tool credentials.
4. Long-running model or tool calls never execute inside a Flowable transaction. They use durable commands, checkpoints, idempotency keys, retries, and explicit terminal states.
5. Backend bounded contexts do not depend on each other's infrastructure. Frontend features do not create uncontrolled cross-feature dependencies.
6. Database changes are append-only Flyway migrations. API changes require an explicit contract and compatibility assessment.
7. Quality gates must be strengthened as the project grows; a failing rule must not be bypassed by lowering thresholds or disabling checks.

## Remaining risks

| Priority | Risk | Required direction |
| --- | --- | --- |
| P0 | Authentication and browser sessions are not yet an enterprise identity solution | Add revocation, rotation, secure browser sessions, and an OAuth 2.1/OIDC provider boundary |
| P0 | Observability and workflow audit are incomplete | Add trace IDs, structured logs, metrics, alerts, immutable workflow audit, and failed-command operations |
| P0 | Frontend CI and real full-stack E2E are missing | Run the frontend quality gate and real PostgreSQL/Redis/backend workflow scenarios in CI |
| P1 | Backend runtime services and frontend views/styles are growing too large | Split by use case, domain policy, adapter, composable, and reusable component |
| P1 | API models are maintained manually across repositories | Adopt OpenAPI, compatibility checks, and generated or validated client contracts |
| P1 | Tenant isolation still depends heavily on correct application queries | Add repository-level defaults, comprehensive negative tests, and evaluate PostgreSQL RLS |
| P1 | Test coverage gates are below the desired production baseline | Raise line and branch thresholds progressively around security, tenancy, concurrency, and recovery |
| P2 | Workflow product capabilities remain incomplete | Add task center, organization directory, groups, forms, notifications, delegation, SLA, and escalation |
| P2 | Agent Runtime has no implemented domain model | Design durable runs, steps, checkpoints, provider credentials, tool policies, human approval, cost limits, and audit before code |

## Required implementation order

### 1. Harden the platform

- Complete identity/session security, tracing, metrics, audit, alerting, backups, and recovery procedures.
- Establish OpenAPI contracts and real full-stack CI scenarios.
- Raise test coverage and verify tenant isolation across every aggregate and operation.
- Add an operational view for failed asynchronous commands and safe manual recovery.

### 2. Complete workflow product foundations

- Introduce task inboxes, organization and group models, form versions, notifications, delegation, SLA, and escalation.
- Keep process definitions, assignment rules, and forms explicitly version-compatible.
- Refactor large backend services and frontend pages before adding more responsibilities to them.

### 3. Build the Agent Runtime

- Create durable `AgentDefinition`, `AgentRun`, `AgentStep`, checkpoint, and execution-event models.
- Isolate model providers and encrypted credentials behind application ports.
- Govern every tool with schema validation, tenant permissions, idempotency, timeout, audit, and optional human approval.
- Integrate agent execution with BPMN through durable events or commands, never hidden in-process state.
- Support pause, resume, cancel, retry, compensation, budget limits, and reproducible model/prompt version evidence.

### 4. Add higher-level experiences

- Build kanban, copilot, and Dify-like authoring experiences on the same identity, tenancy, audit, runtime, and design-system foundations.
- Do not create separate security models or execution engines for different user interfaces.

## Cross-repository definition of done

Every material change must:

- identify its bounded context, tenant scope, permission, audit, transaction, idempotency, and failure-recovery behavior;
- update backend contracts, frontend models, cache invalidation, documentation, and migrations together when applicable;
- include unit tests for business rules and integration/E2E tests for infrastructure boundaries and critical user paths;
- pass repository verification commands without weakening lint, architecture, security, or coverage rules;
- avoid secrets, production credentials, internal stack traces, and implementation-specific workflow variables in user-facing interfaces;
- update the relevant governance document or architecture decision before introducing a new platform-wide pattern;
- update this repository's submodule references only after the corresponding frontend and backend commits are pushed and verified.

The absence of a completed Agent Runtime is a reason to preserve these boundaries more carefully, not a reason to introduce temporary shortcuts into `agent-engine` or the workflow runtime.
