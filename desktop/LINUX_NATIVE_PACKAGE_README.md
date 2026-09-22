# RavenTech OSINT Desktop 5.0.0-rc6 — Linux x86_64 local package

This is an unsigned private test package, not a public release. It contains the Tauri desktop and fixed PyInstaller backend/worker. PostgreSQL remains external and required. Redis/Celery and Docker remain optional compatibility components in native desktop mode.

Configure `$XDG_CONFIG_HOME/raventech-osint/.env` (or `~/.config/raventech-osint/.env`) with a host-reachable PostgreSQL URL and apply the current Alembic migrations. Start `./raventech-osint-desktop`; Tauri supervises its owned backend and worker. Runtime state, logs, and stop markers use XDG state paths. It does not install systemd units or login autostart.

Use Local Runtime to inspect process ownership and health. Stop/restart is available only for children owned by this desktop and requires confirmation. An unrelated process on port 8000 is never terminated. No PostgreSQL data, credentials, user reports, or project data are included.

Linux WSL testing is Linux runtime evidence, not clean-machine acceptance. No public release, signing, updater, or Knowledge ingestion is included.
