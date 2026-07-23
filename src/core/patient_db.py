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
            # For JSON, we instantiate JSONPatientRepository with default DB_PATH
            _repository = JSONPatientRepository(DB_PATH)
        else:
            raise ValueError(
                f"Unknown PATIENT_STORAGE_BACKEND value '{backend}'. "
                "Supported backends are 'json' and 'postgres'."
            )
    return _repository


def _init_db() -> None:
    """Delegates to active repository to initialize database."""
    get_repository()._init_db()


def load_patient(patient_id: str) -> Optional[Dict]:
    """Loads patient data (name, dob, gender, persona) from active storage backend."""
    return get_repository().load_patient(patient_id)


def save_patient(patient_id: str, patient_data: Dict):
    """Saves or updates patient data in active storage backend."""
    get_repository().save_patient(patient_id, patient_data)


def get_patient_name(patient_id: str) -> Optional[str]:
    """Loads a patient name from active storage backend."""
    return get_repository().get_patient_name(patient_id)


def get_all_patient_names() -> List[str]:
    """Returns list of all 'First Last' names currently in DB from active backend."""
    return get_repository().get_all_patient_names()


def get_patient_names_bulk(patient_ids: List[str]) -> Dict[str, str]:
    """
    Returns {patient_id: 'First Last'} for the given IDs in a single DB operation.
    IDs not found in the DB are omitted; the caller should fall back to 'Patient {id}'.
    """
    return get_repository().get_patient_names_bulk(patient_ids)


def list_patient_ids() -> List[str]:
    """Returns list of all patient IDs currently in DB from active backend."""
    return get_repository().list_patient_ids()


def delete_patient(patient_id: str, archive_dir: str | None = None) -> bool:
    """Removes a patient record from active storage backend."""
    return get_repository().delete_patient(patient_id, archive_dir=archive_dir)


def reset_database() -> None:
    """Wipes database/storage in active storage backend."""
    get_repository().reset_database()


def compact_patients(patient_ids: Set[str], max_text: int, max_bio: int, dry_run: bool) -> int:
    """Compacts text/bio fields in active storage backend."""
    return get_repository().compact_patients(patient_ids, max_text, max_bio, dry_run)
