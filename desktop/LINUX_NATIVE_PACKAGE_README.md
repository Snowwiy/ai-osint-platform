# RavenTech OSINT Desktop 5.0.0-rc6 — Linux x86_64 local package

This is an unsigned private test package, not a public release. It contains the Tauri desktop, fixed PyInstaller backend/worker, and PostgreSQL 16 runtime. Fresh native installs use managed loopback PostgreSQL; existing external databases remain supported. Redis/Celery and Docker remain optional compatibility components in native desktop mode.

An existing `$XDG_CONFIG_HOME/raventech-osint/.env` (or `~/.config/raventech-osint/.env`) with `DATABASE_URL` preserves external mode. A fresh install starts a managed PostgreSQL 16 cluster on loopback port 55432, runs forward migrations, then supervises the backend and worker. Runtime state, logs, and stop markers use XDG state paths. It does not install systemd units or login autostart.

Use Local Runtime to inspect process ownership and health. Stop/restart is available only for children owned by this desktop and requires confirmation. An unrelated process on ports 8000 or 55432 is never terminated. User database data, credentials, reports, and project data are not included.

Linux WSL testing is Linux runtime evidence, not clean-machine acceptance. No public release, signing, updater, or Knowledge ingestion is included.
