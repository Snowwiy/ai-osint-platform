# Human-approved Action Gateway

RavenTech routes its supported operational changes through a single Action
Gateway. The gateway stores a proposal first; a proposal is inert and does not
change a service, process, alert, LAN asset, or job.

## Review and approval

Before approving, review the action, target, current target snapshot,
preconditions, reason, supporting evidence references, expected effect, possible
impact, recovery guidance, and expiration. The proposal is bound to a canonical
SHA-256 hash. Approval is authenticated, role-checked, short-lived, single-use,
and tied to that hash and the target snapshot. High-risk local actions require
typing the exact confirmation phrase.

Immediately before execution RavenTech rechecks policy, RBAC, expiry, proposal
integrity, target identity, current state, and concurrency. A changed or missing
target cancels execution and requires a fresh proposal. The executor is selected
from a fixed registry; payload text cannot select a function, module, command, or
executable. The result is checked against the expected postcondition and the
outcome is audited. A completed process call is not described as successful
unless its postcondition is verified.

## Supported action scope

- Start, stop, or restart an enumerated, actionable service on the local RavenTech
  host. Protected/core services and RavenTech-managed runtime services are
  unavailable through this gateway.
- Terminate one selected non-protected local process, after validating PID,
  process name, and stable start identity. The operating system and RavenTech
  protect critical processes.
- Acknowledge an existing RavenTech monitoring alert; the alert remains in
  history.
- Authorize, reject, or return a representable discovered LAN asset to review.
- Queue existing bounded private-LAN discovery or service-observation jobs for
  configured/authorized scope.
- Recompute posture or retry an eligible, fixed-registry RavenTech job.

LAN actions target RavenTech records and bounded local discovery jobs. They do
not control the remote device. Endpoint agents remain telemetry-only.

## AI boundary

The AI Console retains its fixed read-only evidence tools. In a normal model chat,
it may receive a separate proposal-only tool when the current authenticated user
explicitly asks for a specific registered action. The server checks the current
message for action-specific intent and derives local service/process snapshots
from supplied desktop inventory. Missing, protected, or unavailable targets are
refused. The model can create at most one pending proposal per turn. It receives
no approval, execution, shell, filesystem-write, arbitrary HTTP, or remote
administration tool. Text such as “yes” never approves a proposal. Deterministic
analysis workflows and the direct read-only tools endpoint cannot create action
proposals.

Only a human using the authenticated RavenTech interface can review, approve,
reject, and trigger the fixed executor. An AI recommendation, model confidence,
administrator role, local model, or prior approval cannot replace that step.

## RBAC and kill switch

Analyst permissions are limited to the registered low-risk alert acknowledgement
where policy allows. Local service/process control, LAN trust decisions, bounded
discovery, posture actions, and job retry require an administrator. Administrators
remain subject to protected-target rules and approval. An administrator can
disable the gateway globally; pending proposals and approvals are invalidated.

## Failure and recovery

The UI displays safe error codes for stale state, expired approvals, policy
disablement, protected targets, provider unavailability, and unverified
postconditions. Refresh inventory and create a new proposal when the target
changes. Do not retry an ambiguous service/process operation automatically. For a
service that remains in an unexpected state, inspect it locally and decide
whether to create a new proposal.

The gateway never provides generic shell/Python execution, arbitrary imports,
remote commands or termination, router control, public scanning, credential
testing, exploitation, privilege escalation, firewall changes, or persistence.

## Validation scope

Automated tests use synthetic service/process identities and isolated records.
They test approval binding, role checks, target revalidation, replay prevention,
locks, postcondition verification, auditing, protected-target refusal, and the
AI proposal-only boundary. Live Windows/Linux service actions are not required
when no harmless disposable test service is available; critical system services
must never be used as test targets.
