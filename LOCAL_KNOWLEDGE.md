# Local Knowledge and Obsidian

RavenTech Knowledge provides local document ingestion, provenance-aware search,
and stable citations without requiring an external AI service.

## Add a source

An administrator can select an Obsidian vault or a set of reference documents
from the native Knowledge picker. For a selected vault, RavenTech stores its
canonical local root privately in the local database so a manual Sync can
re-read that folder. The path is not returned by APIs, shown in the UI, or
written to audit events. RavenTech walks only the selected root and does not
inspect neighboring directories. The original vault is read-only from
RavenTech's perspective and is never deleted or modified. Selecting individual
documents instead stores their bytes in a private RavenTech-managed snapshot.

Supported formats are Markdown, TXT, PDF, DOCX, HTML, JSON, and CSV. The parser
has configured per-file and aggregate size limits. Executables and unsupported
types are skipped. There is no OCR or image-content extraction. Obsidian
frontmatter is parsed with a small non-executable subset; tags, aliases,
headings, wikilinks, and one bounded level of supported embeds are retained.
Plugin/configuration directories are excluded.

## Trust, review, and provenance

Import does not prove that content is true. A new source defaults to unknown
trust and unverified status. An authorized administrator may set the publisher,
canonical reference URL, publication date, version, language, notes, trust, and
verification after review. Canonical URLs are metadata only and are not fetched.

Documents and chunks retain the source ID/name, relative filename, SHA-256 hash,
modified/indexed times, category, language, tags, trust, verification, heading,
and page number where the parser can establish one. Same-hash copies remain
separate source records and identify an exact duplicate instead of silently
merging provenance.

## Search and citations

Keyword search and metadata filters work locally. Semantic/vector matching is
optional; RavenTech does not download embedding models automatically and falls
back to keyword search if local embeddings are unavailable. Results display a
stable `knowledge:<document-id>` reference and source context. Obsidian links
are used only as explicit navigation relationships, not as inferred facts.

Knowledge is not sent to external AI providers automatically. Reports include
custom Knowledge documents only if the operator selects them in the report
form. Sensitive-content warnings are visible and require an explicit report
confirmation. Citations use relative document names and do not expose local
absolute paths.

## Sync, removal, and recovery

Vault indexing is not a background filesystem watcher. Use Sync to read the
selected vault again. The local source remains available while the vault is
offline; existing indexed content is preserved and the source is reported
offline until it is reachable again. If the vault moves, use the native picker
to relink the source. File-by-file document imports remain app-managed
snapshots and can be refreshed by selecting the changed files again. SHA-256
comparison skips unchanged documents;
changed files replace their chunks, unique-hash renames preserve identity,
removed selected files are removed from the RavenTech index, and links are
reconciled. Source removal requires confirmation and deletes only the managed
RavenTech snapshot after its ownership marker and storage boundary are
validated. If that validation fails, the snapshot is preserved.

Ingestion runs through the fixed `knowledge.source.sync` PostgreSQL worker job.
Job payloads contain source IDs only, not source paths or document bytes.
Operations Center reports source/document/chunk totals, failed and offline
sources, recent sync state, and active indexing jobs without showing content.
Parser/index failures degrade the Knowledge subcomponent but do not make the
backend unhealthy while core storage is available.

## Access and privacy

Source creation, refresh, trust/verification changes, disable, and removal are
administrator-only and audited. Search and document viewing use the current
authenticated Knowledge access model. Audit events contain identifiers and
sanitized counts/state, never document contents, secrets, or absolute source
paths. Source snapshots live in RavenTech's application data storage and follow
the local database/storage backup policy; the original Obsidian vault is not
part of RavenTech backups.
