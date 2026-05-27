# Design Spec: RavenTech OSINT Platform

> **Date:** 2026-05-26
> **Status:** Approved — ready for implementation planning
> **Author:** Brayan "Raven" Gutierrez · RavenTech

---

## Problem Statement

Raven needs a portfolio-grade, production-worthy OSINT and threat intelligence platform for authorized, defensive digital footprint analysis. The platform must be operable by a small team (2–10 analysts), map findings to cybersecurity frameworks (MITRE ATT&CK, OWASP, NIST CSF, ISO 27001), and include full audit logging and a legal/ethical guardrail layer.

---

## Decisions Made

| Question | Decision | Rationale |
|----------|---------|-----------|
| Architecture | Modular Monolith with Plugin Adapters | Best balance of speed + future-proofing for a small team |
| Primary users | Small team (2–10), admin/analyst roles | Drives JWT auth + RBAC + team investigation sharing |
| OSINT sources | 11 sources (see below) | Mix of free + paid, covers all target types |
| AI provider | Claude 3.5 Sonnet (Anthropic) | Best alignment, structured output, ethical stance |
| Embedding model | sentence-transformers all-MiniLM-L6-v2 | Free, local, no external dep for RAG retrieval |
| Database | PostgreSQL 16 | ACID, JSONB for raw findings |
| Vector store | ChromaDB | Python-native, simple Docker setup |
| Task queue | Celery + Redis | Async OSINT jobs without blocking API |
| Deployment | Docker Compose → Cloud VPS | Single-server for MVP, easy ops |
| Frontend | React + Vite + TypeScript + shadcn/ui | Standard, productive, accessible |

---

## OSINT Sources (11 total)

| Source | Cost | Supported target types |
|--------|------|------------------------|
| WHOIS/RDAP | Free | domain, org |
| DNS + crt.sh | Free | domain |
| AlienVault OTX | Free (API key) | domain, IP, URL |
| URLScan.io | Free (API key) | domain, URL |
| GitHub OSINT | Free (rate limited) | domain, org |
| VirusTotal | Freemium | domain, IP, URL |
| AbuseIPDB | Freemium | IP |
| Shodan | Paid | IP, domain |
| SecurityTrails | Paid | domain |
| Censys | Paid | IP, domain |
| HaveIBeenPwned | Paid | email |

---

## Approved Architecture

**See ARCHITECTURE.md for full diagram, folder structure, technology stack, and data flows.**

Key points:
- FastAPI modular monolith: routes → services → adapters (no reverse)
- Each OSINT source = one Python file implementing `BaseOsintAdapter` ABC
- Celery workers handle all slow operations (OSINT fetching, AI analysis, PDF generation)
- RAG: sentence-transformers embed findings → ChromaDB query → Claude synthesis
- RAG knowledge base seeded from existing Obsidian wiki (MITRE/OWASP/NIST/ISO pages)

---

## MVP Scope (v1.0 in ~14 weeks)

**In scope:** All 11 adapters, auth + RBAC, investigation/target/finding management, AI analysis, PDF reports, audit logging, React dashboard, Docker Compose deployment.

**Out of scope:** SSO, mobile app, real-time WebSocket updates, ML-based scoring, public API, scheduled scans, threat actor correlation.

---

## Files Written

All detailed specifications are in the project root:

- `ARCHITECTURE.md` — system design, folder structure (complete), tech stack, data flows, module boundary rules
- `DATABASE_SCHEMA.md` — ER diagram, full SQL for all 12 tables, indexes, retention policy
- `API_SPEC.md` — all endpoints with request/response schemas, rate limits, error codes
- `SECURITY_MODEL.md` — threat model (18 threats), RBAC, auth flow, safe-use policy, security checklist
- `MVP_ROADMAP.md` — 5 phases, 56 GitHub issues grouped by milestone, definition of done
- `CODEX_HANDOFF.md` — complete coding standards, key interfaces, starting sequence, environment config

---

## Next Step

Invoke `writing-plans` skill to create the Phase 0 implementation plan.
