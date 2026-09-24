# RavenTech OSINT Desktop 5.0.0-rc6 — Linux x86_64 local package

This is an unsigned private test package, not a public release. It contains the Tauri desktop, fixed PyInstaller backend/worker, and PostgreSQL 16 runtime. Fresh native installs use managed loopback PostgreSQL; existing external databases remain supported. Redis/Celery and Docker remain optional compatibility components in native desktop mode.

An existing `$XDG_CONFIG_HOME/raventech-osint/.env` (or `~/.config/raventech-osint/.env`) with `DATABASE_URL` preserves external mode. A fresh install starts a managed PostgreSQL 16 cluster on loopback port 55432, runs forward migrations, then supervises the backend and worker. Runtime state, logs, and stop markers use XDG state paths. It does not install systemd units or login autostart.

Use Local Runtime to inspect process ownership and health. Stop/restart is available only for children owned by this desktop and requires confirmation. An unrelated process on ports 8000 or 55432 is never terminated. User database data, credentials, reports, and project data are not included.

## Runtime requirements and validation

The bundle is a portable x86_64 directory package; it does not install a DEB or
RPM and does not create a system service. It requires the external Linux shared
libraries listed by `native-runtime/postgresql/manifest.json` plus the normal
GTK/WebKitGTK libraries required by the Tauri WebKitGTK host. The package
manifest currently records a minimum glibc of 2.38. No Python, Node, Vite,
Docker, Redis, Celery, system PostgreSQL, or PostgreSQL command-line tools from
`PATH` are required for native startup.

Debian 13 x86_64 under WSL2 has passed package validation and packaged runtime
core validation: Tauri process launch, isolated XDG data paths, managed
PostgreSQL 16.15 bootstrap/reuse, migrations, backend readiness, native worker,
and authenticated API workflows. systemd and system D-Bus were available. The
packaged UI was launched under WSLg, but visual interaction was not validated.
This is not clean-machine installation acceptance. Other distributions and
their GUI-library compatibility remain untested; confirm the manifest's
external library requirements before installing the package.

No public release, signing, updater, persistent system service, or
Knowledge/Obsidian ingestion is included.
