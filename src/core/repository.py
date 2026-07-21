from typing import Dict, Any, Optional, List, Set

class PatientRepository:
    """Base interface for patient storage operations."""

    def _init_db(self) -> None:
        """
        Initializes/checks the database setup. Default to no-op.
        """
        pass

    def load_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """
        Loads patient data (name, dob, gender, persona) by patient_id.
        Returns None if not found.
        """
        raise NotImplementedError

    def save_patient(self, patient_id: str, patient_data: Dict[str, Any]) -> None:
        """
        Saves or updates patient data in the storage.
        """
        raise NotImplementedError

    def get_patient_name(self, patient_id: str) -> Optional[str]:
        """
        Loads a patient and returns their full name ('First Last').
        """
        raise NotImplementedError

    def get_all_patient_names(self) -> List[str]:
        """
        Returns a list of all 'First Last' names currently in the storage.
        """
        raise NotImplementedError

    def list_patient_ids(self) -> List[str]:
        """
        Returns a list of all patient IDs (as strings) currently in the storage.
        """
        raise NotImplementedError

    def delete_patient(self, patient_id: str, archive_dir: str | None = None) -> bool:
        """
        Removes a patient record from the database.
        Optionally archives the data to a file inside the archive_dir if provided.
        """
        raise NotImplementedError

    def reset_database(self) -> None:
        """
        Wipes the database/storage to a completely empty state.
        """
        raise NotImplementedError

    def compact_patients(self, patient_ids: Set[str], max_text: int, max_bio: int, dry_run: bool) -> int:
        """
        Prunes/truncates long text and bio narrative fields in patient records.
        If patient_ids is empty, runs on all patients.
        Returns the number of updated patient records.
        """
        raise NotImplementedError
