# Known Limitations & Tracked Future Work

This file records deferred improvements that are out of scope for the current release
but must not be forgotten. Each entry has enough detail to act on without needing to
re-read the surrounding code.

---

## KL-001 — auth-upgrade: Per-user DB-backed API key lookup

**Files:** `backend/app/core/security.py`, `backend/app/core/config.py`

**Current state:** Authentication uses a single server-wide `API_KEY` environment
variable. `core/security.py: verify_api_key()` compares the incoming header against
`settings.api_key` via `secrets.compare_digest`. This is sufficient for a
single-professor self-hosted install.

**What needs to change:**

1. Add a `users` table (Alembic migration) with `id`, `display_name`, and `api_key`
   (hashed) columns.
2. Add `UserRepository.get_by_api_key(key: str) -> User | None` in
   `backend/app/db/repositories/`.
3. Replace the `secrets.compare_digest` check in `verify_api_key()` with a DB lookup
   returning the `User` domain entity.
4. Update `api/deps.py` so `CurrentUser` carries the full `User` entity, not a raw
   string. No endpoint code changes are needed — the interface is intentionally thin.
5. Remove `api_key` from `core/config.py` once the DB-backed path is live.

**Acceptance criteria:** multiple users each have their own key; `make test` covers
valid key, invalid key, and missing key; no changes to any `api/v1/*.py` route handler.

**Why deferred:** The primary user is a single professor. Per-user keys add a
migration + a new repository and require deciding on key hashing (bcrypt vs SHA-256
HMAC). Worth doing before onboarding a second faculty member.

**Referenced from:** `core/security.py` and `core/config.py` TODO comments.

---

## KL-002 — OIDC / SSO upgrade path

**Files:** `backend/app/core/security.py`

**Current state:** The auth interface in `core/security.py` is deliberately minimal —
`verify_api_key()` returns a user identifier and nothing else — so that OIDC or SSO
can be added later without rewriting endpoints.

**What needs to change:** Add an OIDC provider (e.g., Keycloak, Auth0, or Google
Workspace) behind the existing `verify_api_key` abstraction. The endpoint layer calls
`deps.CurrentUser`; that dependency is the only thing that changes.

**Why deferred:** OIDC adds an external dependency and a significant setup burden for a
self-hosted single-user tool. Revisit when the secondary-user (TA / other faculty)
scenario becomes concrete. See PROJECT_BRIEF §7.4.

**Referenced from:** `core/security.py` TODO comment (same location as KL-001).
