# Changelog

All notable changes to the Clinical Data Generator project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to Semantic Versioning.

---
## [8.2.1] - 2026-07-23

### Fixed
- Fixed frontend script execution crash in `ui/index.html` by removing event listener for deleted `batch-purge-modal` and cleaning up dangling tracker export and duplicated functions.
- Resolved backend `/api/patients` endpoint crash in `api_server.py` by adding connection error handling and fallback name placeholder (`Patient {id}`) when PostgreSQL database is offline/unreachable.

---

## [8.2.0] - 2026-07-23

### Added
- Expanded PostgreSQL schema with tables for `insurance_providers`, `insurance_plans`, and `cpt_code_map` (`src/core/schema.sql`).
- PostgreSQL repository methods to load and save insurance and CPT map configs (`src/core/postgres_repository.py`).
- Unified bidirectional migration utility `migrate_data.py` supporting sync strategies.
- DB status connection indicator and ribbon error banner (`#db-error-banner`) in `ui/index.html`.

### Changed
- Refactored `/api/status` in `api_server.py` to check active database connections.

### Removed
- Removed legacy `src/doc_generation/patient_tracker_export.py`, legacy migration scripts, and associated UI elements.

---

## [8.1.0] - 2026-07-21

### Added
- Root-level CLI launcher `run.py` to bootstrap the interactive CLI environment.
- Unit test suite coverage for PostgreSQL schema name validation inside `tests/test_repository.py`.
- Deployment and rollback checklist (`RELEASE_CHECKLIST.md`).

### Changed
- Fixed import path in `src/remove_persona.py` from `from purge_manager import` to `from utils.purge_manager import` to resolve `ModuleNotFoundError`.
- stage files and run full test suites verifying clean execution.

### Removed
- Obsolete empty `patients_db.json` database file from the root directory.
- Legacy `core/.env.example` file (replaced and consolidated under `cred/.env.example`).

---

## [8.0.0] - 2026-07-21

### Added
- **Hybrid Storage Persistence Layer**: Supports both JSON (`json`) and PostgreSQL (`postgres`) backends using `PATIENT_STORAGE_BACKEND` environment toggle.
- **Repository Interface Abstraction**: Decoupled database operations from business logic using `PatientRepository` interface (`src/core/repository.py`).
- **PostgreSQL Repository Implementation**:
  - `PostgresPatientRepository` in `src/core/postgres_repository.py` using `psycopg2`.
  - Self-initializing database DDL schema (`src/core/schema.sql`).
  - GIN indexing on `persona_data` (JSONB) and B-Tree indexes on patient demographics (`last_name`, `first_name`, `dob`).
  - Schema name regex validation in constructor preventing SQL injection vulnerabilities.
  - Runtime DDL initialization guard `_schema_initialized` ensuring database initialization runs exactly once per instance.
- **JSON Repository Implementation**:
  - `JSONPatientRepository` in `src/core/json_repository.py`.
  - Automatically migrates patient databases to a decoupled directory.
- **Bidirectional Migration Scripts**:
  - `migrate_json_to_postgres.py` transfers JSON patient records to PostgreSQL.
  - `migrate_postgres_to_json.py` transfers PostgreSQL records back to local JSON.
  - Built-in conflict resolution strategies (`skip`, `update`, `fail`) selectable via CLI argument.
- Comprehensive integration tests for migration strategies under `tests/test_migration.py` and repository operations under `tests/test_repository.py`.

### Changed
- Relocated active JSON database file to `src/core/patients_db.json` (gitignored).
- Updated log compaction utility `compact_patient_data.py` and selectively purging manager `src/utils/purge_manager.py` to interact with patients DB through repository abstractions instead of direct file I/O.
- Consolidated env-vars configurations under `cred/.env.example`.
