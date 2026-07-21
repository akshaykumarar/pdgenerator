import os
from typing import Optional, Dict, List, Set
from dotenv import load_dotenv

# Load database configuration from cred/.env relative to project root
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_env_path = os.path.join(_project_root, "cred", ".env")
load_dotenv(_env_path)

from .json_repository import JSONPatientRepository
from .postgres_repository import PostgresPatientRepository

DB_PATH = os.path.join(os.path.dirname(__file__), "patients_db.json")

_repository = None

def get_repository():
    """
    Returns the active database repository instance based on PATIENT_STORAGE_BACKEND.
    """
    global _repository
    if _repository is None:
        backend = os.getenv("PATIENT_STORAGE_BACKEND", "json").strip().lower()
        if backend == "postgres":
            # For PostgreSQL, we instantiate PostgresPatientRepository
            _repository = PostgresPatientRepository()
        elif backend == "json":
            # For JSON, we instantiate JSONPatientRepository with the default DB_PATH
            _repository = JSONPatientRepository(DB_PATH)
        else:
            raise ValueError(
                f"Unknown PATIENT_STORAGE_BACKEND value '{backend}'. "
                "Supported backends are 'json' and 'postgres'."
            )
    return _repository

def _init_db() -> None:
    """Delegates to the active repository to initialize the database."""
    get_repository()._init_db()

def load_patient(patient_id: str) -> Optional[Dict]:
    """
    Loads patient data (name, dob, gender, persona) from the active storage.
    Returns None if not found.
    """
    return get_repository().load_patient(patient_id)

def save_patient(patient_id: str, patient_data: Dict):
    """
    Saves or updates patient data in the active storage.
    """
    get_repository().save_patient(patient_id, patient_data)

def get_patient_name(patient_id: str) -> Optional[str]:
    """Loads a patient and returns their full name."""
    return get_repository().get_patient_name(patient_id)

def get_all_patient_names() -> List[str]:
    """
    Returns a list of all 'First Last' names currently in the DB.
    Used to prevent duplicate personas.
    """
    return get_repository().get_all_patient_names()

def list_patient_ids() -> List[str]:
    """
    Returns a list of all patient IDs currently in the DB.
    """
    return get_repository().list_patient_ids()

def delete_patient(patient_id: str, archive_dir: str | None = None) -> bool:
    """
    Removes a patient record from the database.
    Optionally archives the data to a file inside the archive_dir if provided.
    """
    return get_repository().delete_patient(patient_id, archive_dir=archive_dir)

def reset_database() -> None:
    """
    Wipes the database/storage to a completely empty state.
    """
    get_repository().reset_database()

def compact_patients(patient_ids: Set[str], max_text: int, max_bio: int, dry_run: bool) -> int:
    """
    Compacts text/bio fields for specified or all patients.
    Returns the number of updated records.
    """
    return get_repository().compact_patients(patient_ids, max_text, max_bio, dry_run)
