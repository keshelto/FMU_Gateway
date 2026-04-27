# FMU_Gateway Repo Audit (2026-04-27)

## Scope
This audit reviews the current repository and proposes a phased implementation plan to evolve FMU_Gateway into an **agent-native, verified engineering model gateway** without rewriting code in this PR.

---

## 1) Current Architecture

### High-level structure
- `app/` — main public FastAPI gateway (upload FMU, run simulation, payment gating, usage tracking, lightweight library indexing).
- `private-api/` — separate FastAPI service with richer account/licensing/marketplace concepts (currently partially scaffolded).
- `sdk/python/` and `open-sdk/` — two Python SDK trees (overlap and drift risk).
- `shared-specs/` — API contract + pricing tiers intended as interface boundary.
- `deploy/`, `Dockerfile`, `fly.toml` — container and deployment manifests.
- `tests/` — tests primarily targeting `app/main.py` behavior.

### API surface currently implemented
- Main API (`app/main.py`) contains endpoints for:
  - health/root
  - key creation (`/keys`)
  - payment session/tokenization (`/pay`, `/pay/crypto`, webhook + token retrieval)
  - FMU upload/introspection (`/fmus`, `/fmus/{id}/variables`, hash lookup)
  - simulation (`/simulate`)
  - structured simulation retrieval + parameter sweep endpoints
  - engineering calculators (cooling/hydraulic/heat exchanger)
- Library endpoint is implemented in `app/library.py` as `/library` and currently returns `{ "items": [...] }`.

### Runner/model/auth/deployment code locations
- **Runner (public app):** `app/simulate.py` (FMPy wrapper).
- **Runner (private API):** `private-api/app/services/fmu_runner.py` (placeholder deterministic mock, not real FMU execution).
- **Model/domain schemas:**
  - public app: `app/schemas.py`
  - private API: `private-api/app/models/*.py`, `private-api/app/schemas/*.py`
- **Auth:**
  - public app: bearer key validation in `app/main.py` (`verify_api_key`) with env-controlled bypass (`REQUIRE_AUTH`)
  - private API: JWT + API key service in `private-api/app/services/auth_service.py`
- **Deployment:**
  - primary image: root `Dockerfile`
  - compose: `deploy/docker-compose.yml`
  - Fly config: `fly.toml`
  - private API image: `private-api/Dockerfile`

---

## 2) Gaps vs “agent-native verified engineering model gateway” target

1. **Two backends, no single source of truth**
   - `app/` and `private-api/` implement overlapping but divergent product directions.
   - `shared-specs/api_contract.yaml` describes `/execute_fmu`, while public app centers on `/simulate`.

2. **Verification model is incomplete**
   - No first-class concept of model verification status, signer, provenance chain, trust policy, reproducibility attestations, or verification workflow.
   - Existing provenance in `app/main.py` is lightweight and per-run, not registry-grade verification metadata.

3. **Agent-native contract is underspecified**
   - `gateway_interface.yaml` is minimal and not aligned with all live endpoints or strict tool-only policy enforcement semantics.
   - No explicit machine-readable “verified model selection + policy enforcement + audit trace” API layer.

4. **Execution isolation + determinism guarantees are partial**
   - Public app uses FMPy directly with timeout safeguards, but stronger sandbox controls, deterministic replay metadata, and attestation are not formalized.
   - Private runner is a stub (non-production execution path).

5. **Auth/authorization inconsistency**
   - Public `/library` currently appears effectively open in tests despite auth expectations.
   - Private API uses JWT/API key + credits, but no unified policy engine across both services.

6. **Spec/SDK drift risk**
   - Two Python SDK implementations (`sdk/python` and `open-sdk`) plus partially divergent route contracts.

---

## 3) Test health: broken tests and missing tests

## Broken tests (current)
Running `pytest -q` fails with 4 tests:
- `tests/test_auth.py::test_protected_endpoint_without_auth` (expected 401, got 200)
- `tests/test_auth.py::test_invalid_key` (expected 401, got 200)
- `tests/test_library.py::test_get_library` (expected 401, got 200)
- `tests/test_library.py::test_library_search` (TypeError: test expects list item iteration, endpoint returns object with `items` key)

Interpretation:
- Auth behavior for `/library` and response contract for `/library` are currently mismatched with test expectations.

## Missing/insufficient tests
- No dedicated test suite for `private-api/` routes/services.
- No contract tests asserting `shared-specs/api_contract.yaml` compatibility against running services.
- No end-to-end verification lifecycle tests (register model → verify → approve policy → execute with signed provenance).
- No deterministic replay/attestation tests.
- No deployment smoke tests for `deploy/docker-compose.yml` and `fly.toml` in CI.

---

## 4) Keep / Replace / Deprecate recommendation

### Keep (foundation)
- `app/simulate.py` and core simulation flow in `app/main.py` (useful execution foundation).
- `app/validation.py`, `app/storage.py`, `app/db.py` (practical baseline for safety/persistence).
- `shared-specs/` directory concept (good place for canonical contract).
- `tests/` harness and payment simulation tests as starting quality framework.

### Replace / Refactor (incremental)
- Unify API contract to one canonical execution path (likely `/simulate` or `/execute_fmu`, not both as primary).
- Consolidate duplicated SDK trees (`sdk/python` + `open-sdk`) into one maintained SDK.
- Replace private placeholder runner (`private-api/app/services/fmu_runner.py`) with actual isolated execution adapter (without changing in this audit PR).
- Introduce explicit verification registry schema and policy enforcement layer instead of ad-hoc provenance fields.

### Deprecate (after migration)
- One of the two backend app stacks (`app/` vs `private-api/`) after selecting canonical runtime.
- Legacy docs that claim architecture/contracts not matching runtime behavior.
- Redundant scripts/configs that target deprecated stack once migration is complete.

---

## 5) Recommended milestone sequence

### Milestone 0 — Stabilize baseline
- Fix failing auth/library contract tests.
- Freeze and publish single canonical API contract in `shared-specs/`.
- Add compatibility checks in CI (contract vs live endpoints).

### Milestone 1 — Canonical service boundary
- Decide primary backend path (public app or private-api) and mark other as transitional.
- Add adapter layer to keep external API stable while internals converge.

### Milestone 2 — Verified model registry core
- Add model entity fields: verification status, verifier identity, verification artifact hash/signature, approved execution constraints, provenance manifest.
- Add endpoints for verification submission/review/status retrieval.

### Milestone 3 — Agent-native policy + tooling
- Define machine-usable endpoint(s) for: discover verified models, request quote/policy, execute with audit trace.
- Enforce policy gate (only verified models for restricted modes; explicit override modes with trace).

### Milestone 4 — Deterministic execution attestations
- Emit execution receipt containing input hash, model hash, environment fingerprint, and output artifact hashes.
- Add replay endpoint/checker for reproducibility.

### Milestone 5 — Production hardening
- Deployment profile unification, observability, rate-limit consistency, and failure-mode tests.
- Sunset deprecated stack/components.

---

## 6) Key risks
- **Architecture bifurcation risk:** continued divergence of `app/` and `private-api/` increases migration cost.
- **Contract drift risk:** SDK/spec/runtime inconsistency causes agent integration failures.
- **Security/compliance risk:** placeholder/private components may be mistaken as production-ready.
- **Operational risk:** mixed payment/auth semantics can create inconsistent enforcement paths.
- **Adoption risk:** “verified” promise is weak until verification metadata + policy gates are first-class.

---

## 7) Exact next PR task (single, concrete)

**Next PR:**
“Normalize `/library` behavior to match auth + response contract expectations, and make tests green.”

### Required changes in that PR
1. Decide and document `/library` contract shape (list vs `{items: [...]}`) and apply consistently.
2. Enforce API key auth on `/library` (or update tests/spec if intentionally public).
3. Update tests to reflect the chosen contract and access model.
4. Add one contract test that validates `/library` schema to prevent regressions.

### Acceptance for that PR
- `pytest -q` passes in this repo.
- `/library` behavior is explicitly documented in README + shared spec.

---

## Commands to run project locally

### Public gateway (root app)
```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### With SDK editable install
```bash
pip install -e ./sdk/python
```

### Private API
```bash
pip install -r private-api/requirements.txt
cd private-api && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker (compose)
```bash
make build
make run
```

### Tests
```bash
pytest -q
```
