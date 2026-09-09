# RavenTech OSINT Free-Tier Hosting Options

Status: research and pre-hosting planning only, reviewed 2026-09-08.

No deployment, DNS configuration, credential creation, or database migration is
authorized by this document. Provider plans change; re-check every linked
official page immediately before a future implementation phase.

## Option Comparison

| Component | Candidate | Current free-tier fit | Important constraints for this project |
| --- | --- | --- | --- |
| Frontend | [Cloudflare Pages](https://developers.cloudflare.com/pages/platform/limits/) | Strong portfolio/demo candidate for the static Vite build | Free-plan limits include 500 builds/month, one concurrent build, 20,000 files, and 25 MiB per asset. Hosting and DNS remain unconfigured. |
| Frontend | [Vercel Hobby](https://vercel.com/docs/plans/hobby) | Strong personal portfolio candidate | Hobby is free but restricted to non-commercial personal use; limits and fair-use rules apply. Reassess before any client-facing use. |
| Frontend | [Netlify Free](https://www.netlify.com/pricing/) | Suitable alternative for a small static demo | The current Free plan uses a hard 300-credit monthly cap; projects pause when the account reaches the limit. |
| Backend | [Render Free web service](https://render.com/docs/free) | Feasible only for a low-traffic FastAPI preview | It sleeps after 15 idle minutes, cold start can approach a minute, the filesystem is ephemeral, free services can restart, and free background workers are not offered. Local report/Chroma files and Celery therefore need a separately reviewed design. |
| Backend | [Railway Free](https://docs.railway.com/pricing/plans) | Trial or very small preview candidate; feasibility must be measured | After the one-time trial, Free currently provides $1 monthly credit with up to 0.5 GB RAM per service. That may be insufficient for an always-on API plus worker; Hobby is paid. |
| PostgreSQL | [Supabase Free](https://supabase.com/pricing) | Candidate for PostgreSQL only | Current Free limits include two active projects and 500 MB database size; projects can pause after inactivity and automatic backups are not included. Supabase Auth is explicitly out of scope. |
| Redis | [Upstash Redis Free](https://upstash.com/pricing/redis) | Candidate for low-volume cache/broker experiments | Current Free tier lists one database, 256 MB, 500,000 monthly commands, and 10 GB bandwidth. Confirm Redis/TLS and Celery behavior under real worker load before selection. |

## Likely Evaluation Architecture

For a future proof-of-concept review, evaluate:

- static frontend on Cloudflare Pages or Vercel;
- FastAPI backend on Render or Railway only if measured memory, cold-start,
  worker, and filesystem constraints are acceptable;
- Supabase as PostgreSQL only, retaining the application's current backend auth;
- Upstash as Redis only if command limits and Celery compatibility pass testing;
- a custom domain through Cloudflare DNS in a later, separately authorized phase.

This is a candidate topology, not a recommendation to deploy today. Cloudflare
Pages is the leading frontend option for this static Vite build. Neither backend
candidate should be called production-ready on its free tier: the application
currently expects a web process, Celery worker, PostgreSQL, Redis, writable
report storage, and local knowledge/Chroma storage.

## Required Pre-Deployment Decisions

Before any hosting work is approved, document and test:

- persistent report/export and knowledge-vector storage instead of ephemeral
  container files;
- whether Celery remains required for the hosted demo and where its worker runs;
- TLS connection strings, connection pooling, database extension compatibility,
  and Alembic upgrade/rollback procedure;
- provider inactivity, sleep, quota, data-retention, backup, and recovery rules;
- CORS, frontend API base URL, health checks, secret rotation, logging, and
  spending safeguards;
- synthetic-only demo data and a governed registration policy;
- an exit path if a free plan changes or pauses the service.

Before credentials are created, complete `SECRETS_AUDIT_CHECKLIST.md`. Use each
provider's secret store for backend-only values, expose only the public frontend
API base URL to the Vite build, replace the local signing key, and use explicit
HTTPS CORS origins. Never place database, Redis, signing, invite, admin bootstrap,
or AI/provider credentials in frontend environment variables. These are future
requirements only; no provider secrets or services are configured in RC2.

## Non-Negotiable Boundaries

- Do not deploy or configure DNS during Phase 5S.
- Do not add real secrets to Git, images, build logs, or documentation.
- Do not migrate the local database or alter the current migration chain.
- Do not replace current authentication with Supabase Auth.
- Use Supabase only as a future PostgreSQL candidate.
- Do not expose PostgreSQL or Redis directly to browsers.
- Do not claim free-tier uptime, durability, backups, or production suitability.
