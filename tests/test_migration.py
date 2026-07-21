import os
import tempfile
import pytest
from migrate_json_to_postgres import migrate as migrate_to_pg
from migrate_postgres_to_json import migrate as migrate_to_json
from src.core.json_repository import JSONPatientRepository
from src.core.postgres_repository import PostgresPatientRepository


def test_migration_and_reverse_migration(monkeypatch):
    """
    Integration test for JSON to PostgreSQL migration and PostgreSQL to JSON reverse migration.
    Verifies that patient records are transferred successfully, data integrity is preserved,
    and skip, update, and fail strategies for conflicting IDs are handled correctly.
    """
    # 1. Set DB_SCHEMA to pdgenerator_migration_test for isolation during test run
    monkeypatch.setenv("DB_SCHEMA", "pdgenerator_migration_test")

    # 2. Check if DB credentials are set in environment. If not, skip this test.
    if not os.getenv("DB_HOST"):
        pytest.skip("PostgreSQL credentials are not configured in environment variables.")

    # 3. Setup temporary file for test JSON DB
    fd, temp_json_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)

    # Mock LEGACY_DB_PATH to prevent legacy database migration during testing
    nonexistent_path = os.path.join(temp_json_path, "nonexistent")
    monkeypatch.setattr("src.core.json_repository.LEGACY_DB_PATH", nonexistent_path)
    monkeypatch.setattr("core.json_repository.LEGACY_DB_PATH", nonexistent_path)

    # Instantiate test repositories
    dest_json_repo = JSONPatientRepository(temp_json_path)
    postgres_repo = PostgresPatientRepository()

    try:
        # Initialize empty databases
        dest_json_repo._init_db()
        postgres_repo._init_db()
        postgres_repo.reset_database()

        # Add sample patient record to JSON database
        sample_patient = {
            "first_name": "Migration",
            "last_name": "Test",
            "gender": "male",
            "dob": "1999-09-09",
            "bio_narrative": "Patient for migration testing.",
            "diagnoses": []
        }
        dest_json_repo.save_patient("999", sample_patient)

        # Verify initial states
        assert dest_json_repo.load_patient("999") is not None
        assert postgres_repo.load_patient("999") is None

        # 4. Run JSON -> Postgres migration (strategy=update)
        migrate_to_pg(strategy="update", json_path=temp_json_path)

        # Verify record migrated to Postgres database
        loaded_pg = postgres_repo.load_patient("999")
        assert loaded_pg is not None
        assert loaded_pg["first_name"] == "Migration"
        assert loaded_pg["last_name"] == "Test"
        assert loaded_pg["dob"] == "1999-09-09"

        # 5. Modify patient record in PostgreSQL, delete from JSON
        sample_patient_modified = loaded_pg.copy()
        sample_patient_modified["first_name"] = "MigrationModified"
        postgres_repo.save_patient("999", sample_patient_modified)
        dest_json_repo.delete_patient("999")

        assert dest_json_repo.load_patient("999") is None

        # 6. Run Postgres -> JSON reverse migration (strategy=update)
        migrate_to_json(strategy="update", json_path=temp_json_path)

        # Verify modified record migrated back to JSON database
        loaded_json = dest_json_repo.load_patient("999")
        assert loaded_json is not None
        assert loaded_json["first_name"] == "MigrationModified"

        # 7. Test conflict strategies: skip vs update vs fail
        # Modify patient record in JSON again
        loaded_json["first_name"] = "ConflictJSON"
        dest_json_repo.save_patient("999", loaded_json)

        # A: Strategy 'skip'
        # Postgres has 'MigrationModified'. JSON has 'ConflictJSON'.
        # Migrating JSON -> Postgres with strategy='skip' should leave Postgres unchanged.
        migrate_to_pg(strategy="skip", json_path=temp_json_path)
        assert postgres_repo.load_patient("999")["first_name"] == "MigrationModified"

        # B: Strategy 'fail'
        # Migrating JSON -> Postgres with strategy='fail' should raise RuntimeError
        with pytest.raises(RuntimeError):
            migrate_to_pg(strategy="fail", json_path=temp_json_path)

        # C: Strategy 'update'
        # Migrating JSON -> Postgres with strategy='update' should overwrite Postgres
        migrate_to_pg(strategy="update", json_path=temp_json_path)
        assert postgres_repo.load_patient("999")["first_name"] == "ConflictJSON"

    finally:
        # Clean up JSON database test file
        if os.path.exists(temp_json_path):
            try:
                os.remove(temp_json_path)
            except Exception:
                pass

        # Drop the test PostgreSQL schema
        try:
            conn = postgres_repo._connect()
            with conn.cursor() as cur:
                cur.execute(f"DROP SCHEMA IF EXISTS {postgres_repo.schema} CASCADE;")
            conn.commit()
            conn.close()
        except Exception:
            pass
