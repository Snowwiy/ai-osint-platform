# Secrets Audit Checklist

Use this checklist before any future hosting review and after changes to
configuration, automation, backup, or logging. The current validated mode is
local Docker Compose. Hosting and DNS remain deferred, Supabase has not been
migrated or configured, and the platform remains passive and defensive-only.

## Phase 5V Result

- [x] Only `.env.example` and `frontend/.env.example` are tracked environment
  templates; no real `.env` file is tracked.
- [x] No private key blocks, Anthropic/OpenAI-style provider keys, GitHub tokens,
  JWTs, or Supabase service credentials were found in tracked files.
- [x] Credential-shaped PostgreSQL URLs are limited to documented local/CI
  fixtures and placeholders; no production database credential was found.
- [x] `.gitignore` excludes local environment files, database backups, generated
  reports, Python caches, and frontend build/dependency output.
- [x] The frontend environment template exposes only `VITE_API_BASE_URL`.
- [x] Docker Compose keeps database, Redis, signing, invite, bootstrap, and
  provider values in backend/service environment configuration.
- [x] Placeholder signing keys warn locally and fail startup in production mode.
- [x] Production CORS rejects wildcard origins.
- [x] SQL parameter echo is disabled and log-message redaction has regression
  coverage.
- [x] Restore refuses overwrite of live/system databases; demo reset remains
  guarded and limited to fixed synthetic records.

## Safe Review Procedure

Run from the repository root. These commands enumerate tracked configuration
surfaces without printing environment values:

```powershell
git status --short
git ls-files | Where-Object { (Split-Path $_ -Leaf) -like ".env*" }
git ls-files "*.pem" "*.key" "*.p12" "*.pfx"
git check-ignore .env backups/local/example.dump reports_output/example.pdf
git grep -IlE -- "BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|sk-ant-[A-Za-z0-9_-]{16,}|sk-proj-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}" -- .
```

Review every reported filename manually. Expected examples may contain only
obvious local/test values or placeholders. Do not use a command that prints the
matching line when a real credential may be present.

Then verify boundaries:

- [ ] `.env` is untracked and ignored.
- [ ] Documentation and screenshots contain placeholders only.
- [ ] Frontend variables do not include database, Redis, signing, invite,
  bootstrap password, Authorization, or provider secrets.
- [ ] CI uses isolated test-only values and requires no production secret.
- [ ] Backups and exports are ignored, access-restricted, and absent from commits.
- [ ] Logs and diagnostics contain no request bodies, password hashes, tokens,
  authorization headers, or credential-bearing connection URLs.
- [ ] Registration remains disabled by default and approval/invite policy is
  reviewed before any exposure.
- [ ] Production-style configuration uses a unique signing key and explicit
  HTTPS CORS origins.

## If A Secret Is Found

1. Do not print, paste, commit, or share the value.
2. Revoke or rotate it at the source immediately.
3. Remove it from the working tree and replace examples with placeholders.
4. Determine whether it exists in Git history, CI logs, backups, exports, or
   screenshots. Treat it as compromised even after deletion from the current
   file.
5. Coordinate any history rewrite separately; it is destructive for
   collaborators and is not part of the RC3 freeze.
6. Re-run the complete validation gate and document the incident without
   reproducing the credential.

No production secrets are required for the validated local mode. Provider keys
remain optional, and deterministic AI fallback remains available without them.
