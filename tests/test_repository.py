import os
import tempfile
import json
# pyrefly: ignore [missing-import]
import pytest
from src.core.repository import PatientRepository
from src.core.json_repository import JSONPatientRepository
from src.core.postgres_repository import PostgresPatientRepository
from src.core import patient_db

def test_repository_interfaces():
    # Verify that JSON repository is an instance of PatientRepository
    json_repo = JSONPatientRepository()
    assert isinstance(json_repo, PatientRepository)

    # Verify that Postgres repository is an instance of PatientRepository
    pg_repo = PostgresPatientRepository()
    assert isinstance(pg_repo, PatientRepository)


def test_json_repository_operations(monkeypatch):
    # Setup temporary directory for test DB
    temp_path = tempfile.mkdtemp()

    # Mock LEGACY_DB_PATH to prevent automatic legacy database migration during testing
    monkeypatch.setattr("src.core.json_repository.LEGACY_DB_PATH", os.path.join(temp_path, "nonexistent"))

    try:
        repo = JSONPatientRepository(temp_path)
        # 1. Initialize
        repo._init_db()
        assert os.path.exists(temp_path)
        assert os.listdir(temp_path) == []

        # 2. Save and Load
        patient_data = {
            "first_name": "John",
            "last_name": "Doe",
            "gender": "male",
            "dob": "1990-01-01",
            "bio_narrative": "A test bio narration that is relatively short.",
            "diagnoses": [{"code": "I10", "condition": "Essential hypertension"}]
        }
        repo.save_patient("101", patient_data)
        
        loaded = repo.load_patient("101")
        assert loaded is not None
        assert loaded["first_name"] == "John"
        assert loaded["last_name"] == "Doe"

        # 3. Get name
        name = repo.get_patient_name("101")
        assert name == "John Doe"

        # 4. Get all names
        all_names = repo.get_all_patient_names()
        assert "John Doe" in all_names

        # 5. List patient IDs
        ids = repo.list_patient_ids()
        assert "101" in ids

        # 6. Compaction
        # Add a patient record with long bio narrative and long text to test compaction
        long_bio = "X" * 1500
        patient_data_long = {
            "first_name": "Jane",
            "last_name": "Smith",
            "bio_narrative": long_bio,
            "some_long_text": "Y" * 1500
        }
        repo.save_patient("102", patient_data_long)

        # Compact with limit 1000
        updated = repo.compact_patients({"102"}, max_text=1000, max_bio=1000, dry_run=False)
        assert updated == 1
        
        compacted = repo.load_patient("102")
        assert len(compacted["bio_narrative"]) <= 1050  # 1000 + length of suffix
        assert "... (truncated)" in compacted["bio_narrative"]
        assert len(compacted["some_long_text"]) <= 1050
        assert "... (truncated)" in compacted["some_long_text"]

        # 7. Delete patient
        # Delete with archive
        archive_dir = tempfile.mkdtemp()
        deleted = repo.delete_patient("101", archive_dir=archive_dir)
        assert deleted is True
        
        # Verify archived file
        archive_file = os.path.join(archive_dir, "patient_101_db.json")
        assert os.path.exists(archive_file)
        with open(archive_file, "r", encoding="utf-8") as f:
            archived_data = json.load(f)
            assert archived_data["first_name"] == "John"

        # Clean up archive
        os.remove(archive_file)
        os.rmdir(archive_dir)

        # Verify deletion from DB
        assert repo.load_patient("101") is None
        assert "101" not in repo.list_patient_ids()

        # 8. Reset database
        repo.reset_database()
        assert os.listdir(temp_path) == []

    finally:
        if os.path.exists(temp_path):
            import shutil
            shutil.rmtree(temp_path)


def test_postgres_repository_operations(monkeypatch):
    # Set DB_SCHEMA to pdgenerator_test for isolation during test run
    monkeypatch.setenv("DB_SCHEMA", "pdgenerator_test")
    
    # Check if DB credentials are set. If not, skip this test.
    if not os.getenv("DB_HOST"):
        pytest.skip("PostgreSQL credentials are not configured in environment variables.")

    repo = PostgresPatientRepository()
    
    try:
        # 1. Initialize
        repo._init_db()
    except RuntimeError as e:
        pytest.skip(f"PostgreSQL server unreachable: {e}")
        
    try:
        # 2. Reset database
        repo.reset_database()
        assert repo.list_patient_ids() == []

        # 3. Save and Load
        patient_data = {
            "first_name": "Alice",
            "last_name": "Smith",
            "gender": "female",
            "dob": "1985-05-15",
            "bio_narrative": "A test bio narration that is relatively short.",
            "diagnoses": [{"code": "I10", "condition": "Essential hypertension"}]
        }
        repo.save_patient("201", patient_data)
        
        loaded = repo.load_patient("201")
        assert loaded is not None
        assert loaded["first_name"] == "Alice"
        assert loaded["last_name"] == "Smith"

        # 4. Get name
        name = repo.get_patient_name("201")
        assert name == "Alice Smith"

        # 5. Get all names
        all_names = repo.get_all_patient_names()
        assert "Alice Smith" in all_names

        # 6. List patient IDs
        ids = repo.list_patient_ids()
        assert "201" in ids

        # 7. Compaction
        long_bio = "Z" * 1500
        patient_data_long = {
            "first_name": "Bob",
            "last_name": "Jones",
            "bio_narrative": long_bio,
            "some_long_text": "W" * 1500
        }
        repo.save_patient("202", patient_data_long)

        # Compact with limit 1000
        updated = repo.compact_patients({"202"}, max_text=1000, max_bio=1000, dry_run=False)
        assert updated == 1
        
        compacted = repo.load_patient("202")
        assert len(compacted["bio_narrative"]) <= 1050
        assert "... (truncated)" in compacted["bio_narrative"]

        # 8. Delete patient
        deleted = repo.delete_patient("201")
        assert deleted is True
        assert repo.load_patient("201") is None
        assert "201" not in repo.list_patient_ids()

        # 9. Clean up/Reset
        repo.reset_database()
        assert repo.list_patient_ids() == []

    finally:
        # Drop test schema entirely to leave the DB clean
        try:
            conn = repo._connect()
            with conn.cursor() as cur:
                cur.execute(f"DROP SCHEMA IF EXISTS {repo.schema} CASCADE;")
            conn.commit()
            conn.close()
        except Exception:
            pass


def test_factory_delegation(monkeypatch):
    # Test JSON active backend
    monkeypatch.setenv("PATIENT_STORAGE_BACKEND", "json")
    # Reset internal repository singleton to trigger re-instantiation
    patient_db._repository = None
    assert isinstance(patient_db.get_repository(), JSONPatientRepository)

    # Test Postgres active backend
    monkeypatch.setenv("PATIENT_STORAGE_BACKEND", "postgres")
    patient_db._repository = None
    assert isinstance(patient_db.get_repository(), PostgresPatientRepository)

    # Test Invalid active backend
    monkeypatch.setenv("PATIENT_STORAGE_BACKEND", "invalid_backend")
    patient_db._repository = None
    with pytest.raises(ValueError):
        patient_db.get_repository()

    # Reset repository singleton to default (json) after test
    patient_db._repository = None


def test_postgres_schema_validation(monkeypatch):
    """Verify that PostgresPatientRepository validates the DB_SCHEMA environment variable correctly."""
    # Test invalid schema names containing special characters or SQL injection attempts
    monkeypatch.setenv("DB_SCHEMA", "invalid-schema-name")
    with pytest.raises(ValueError) as excinfo:
        PostgresPatientRepository()
    assert "Invalid DB_SCHEMA value" in str(excinfo.value)

    monkeypatch.setenv("DB_SCHEMA", "schema; drop table patients;")
    with pytest.raises(ValueError) as excinfo:
        PostgresPatientRepository()
    assert "Invalid DB_SCHEMA value" in str(excinfo.value)

    # Test valid schema names
    monkeypatch.setenv("DB_SCHEMA", "valid_schema_123")
    repo = PostgresPatientRepository()
    assert repo.schema == "valid_schema_123"

