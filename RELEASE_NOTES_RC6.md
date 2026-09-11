# RavenTech OSINT 5.0.0-rc6

## Desktop-local candidate

RC6 freezes the local desktop first-use experience. It retains the validated
FastAPI, React/Vite, PostgreSQL, Redis, Docker Compose, portable, unsigned NSIS,
controlled-launcher, and private artifact-package architecture from RC5.

## Setup wizard

- Adds a three-stage English/Spanish wizard for Project, Prerequisites, and
  Local services.
- Shows validated project-path, approved-script, Docker, backend, frontend,
  release, migration, and ports 8000/5173 state with one next action.
- Improves empty/invalid-path messages and command-copy failure guidance.
- Clarifies that portable and installed builds share the same validated path.
- Adds loopback-only Windows firewall guidance.

The wizard does not install Docker or other prerequisites, edit `.env`, reset
data, modify firewall settings, or start a service automatically.

## Local artifacts

The ignored RC6 portable executable, unsigned installer, and private aggregate
package retain strict file allowlists, SHA-256 manifests, and exclusion checks.
They do not bundle the backend, PostgreSQL, Redis, Docker, credentials, reports,
backups, logs, or local configuration.

## Release boundary

`v5.0.0-rc6` identifies a validated local candidate only. There is no public
release, code signing, auto-update, hosting, deployment, DNS, Supabase migration,
router automation, arbitrary shell execution, remote administration, remote
command execution, new scanning, or offensive functionality.
