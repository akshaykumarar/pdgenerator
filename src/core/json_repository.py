import json
import os
import shutil
from typing import Dict, Any, Optional, List, Set, Tuple
from .repository import PatientRepository

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEGACY_DB_PATH = os.path.join(PROJECT_ROOT, "core", "patients_db.json")
DB_DIR = os.path.join(os.path.dirname(__file__), "patients_db")

def _truncate(text: str, max_len: int) -> str:
    """Truncates text to max_len and adds a suffix if needed."""
    if not text or max_len <= 0:
        return text
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + " ... (truncated)"

def _compact_value(value: Any, max_text: int, max_bio: int, key: str | None = None) -> Tuple[Any, int]:
    """Recursively compacts strings in a JSON-like object."""
    truncated_count = 0
    if isinstance(value, str):
        limit = max_bio if key == "bio_narrative" else max_text
        new_val = _truncate(value, limit)
        if new_val != value:
            truncated_count += 1
        return new_val, truncated_count
    
    if isinstance(value, list):
        new_list = []
        for item in value:
            new_item, t = _compact_value(item, max_text, max_bio)
            truncated_count += t
            new_list.append(new_item)
        return new_list, truncated_count
    
    if isinstance(value, dict):
        new_dict = {}
        for k, v in value.items():
            new_v, t = _compact_value(v, max_text, max_bio, key=str(k))
            truncated_count += t
            new_dict[k] = new_v
        return new_dict, truncated_count
    
    return value, truncated_count

class JSONPatientRepository(PatientRepository):
    """Local JSON file-per-patient implementation of PatientRepository."""

    def __init__(self, db_dir: Optional[str] = None):
        self.db_dir = db_dir or DB_DIR
        self._init_db()

    def _migrate_legacy_db(self) -> bool:
        """Migrate legacy patient DB from a single JSON file to a directory structure."""
        if not os.path.exists(LEGACY_DB_PATH):
            return False
        
        try:
            with open(LEGACY_DB_PATH, "r", encoding="utf-8") as f:
                legacy_data = json.load(f)
            
            if not isinstance(legacy_data, dict) or not legacy_data:
                return False

            for patient_id, patient_data in legacy_data.items():
                self.save_patient(patient_id, patient_data)

            # Optional: Rename the legacy file to prevent re-migration
            try:
                os.rename(LEGACY_DB_PATH, LEGACY_DB_PATH + '.migrated')
                print(f"   🔁 Renamed legacy DB to {os.path.basename(LEGACY_DB_PATH)}.migrated")
            except OSError as e:
                print(f"   ⚠️ Could not rename legacy DB file: {e}")

            print(f"   🔁 Migrated {len(legacy_data)} patient(s) from legacy DB.")
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to migrate legacy patient DB: {e}")

    def _init_db(self):
        """Initialize the database directory and run migration if needed."""
        if not os.path.exists(self.db_dir):
            os.makedirs(self.db_dir)
            print(f"   ✅ Created patient DB directory at {self.db_dir}")

        # Run migration if legacy file exists and the new DB is empty
        if not os.listdir(self.db_dir):
            self._migrate_legacy_db()

    def _get_patient_path(self, patient_id: str) -> str:
        """Get the file path for a given patient ID."""
        return os.path.join(self.db_dir, f"{patient_id}.json")

    def load_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        patient_path = self._get_patient_path(patient_id)
        if not os.path.exists(patient_path):
            return None
        try:
            with open(patient_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"   ⚠️  Warning: Patient file for {patient_id} is corrupted. Error: {e}")
            return None # Or handle corruption differently
        except Exception as e:
            raise RuntimeError(f"Failed to load patient {patient_id} from JSON DB: {e}")

    def save_patient(self, patient_id: str, patient_data: Dict[str, Any]) -> None:
        patient_path = self._get_patient_path(patient_id)
        
        # If a partial update is intended, load existing data first
        existing_data = self.load_patient(patient_id) or {}
        existing_data.update(patient_data)
        
        try:
            with open(patient_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2)
        except Exception as e:
            raise RuntimeError(f"Failed to save patient {patient_id} to JSON DB: {e}")
        
        print(f"      💾 Patient {patient_id} ({existing_data.get('name', 'Unknown')}) saved to JSON DB.")

    def get_patient_name(self, patient_id: str) -> Optional[str]:
        p = self.load_patient(patient_id)
        if p:
            first = p.get('first_name', '')
            last = p.get('last_name', '')
            if first or last:
                return f"{first} {last}".strip()
            return p.get('name')
        return None

    def get_all_patient_names(self) -> List[str]:
        names = []
        for patient_id in self.list_patient_ids():
            name = self.get_patient_name(patient_id)
            if name:
                names.append(name)
        return names

    def list_patient_ids(self) -> List[str]:
        if not os.path.exists(self.db_dir):
            return []
        try:
            return [f.split('.')[0] for f in os.listdir(self.db_dir) if f.endswith('.json')]
        except Exception as e:
            raise RuntimeError(f"Failed to list patient IDs from JSON DB: {e}")

    def delete_patient(self, patient_id: str, archive_dir: str | None = None) -> bool:
        patient_path = self._get_patient_path(patient_id)
        if not os.path.exists(patient_path):
            print(f"      ℹ️  ID {patient_id} not found in DB.")
            return False

        if archive_dir:
            if not os.path.exists(archive_dir):
                os.makedirs(archive_dir)
            archive_path = os.path.join(archive_dir, f"patient_{patient_id}_db.json")
            try:
                shutil.copyfile(patient_path, archive_path)
                print(f"      ✅ Archived DB entry to: {os.path.basename(archive_path)}")
            except Exception as e:
                raise RuntimeError(f"Failed to archive patient DB entry: {e}")

        try:
            os.remove(patient_path)
            print(f"      ✅ Removed from DB: {patient_id}")
            return True
        except OSError as e:
            raise RuntimeError(f"Failed to delete patient file: {e}")

    def reset_database(self) -> None:
        if os.path.exists(self.db_dir):
            try:
                shutil.rmtree(self.db_dir)
            except OSError as e:
                raise RuntimeError(f"Failed to remove database directory: {e}")
        self._init_db()

    def compact_patients(self, patient_ids: Set[str], max_text: int, max_bio: int, dry_run: bool) -> int:
        updated_count = 0
        target_ids = patient_ids or set(self.list_patient_ids())

        for pid in target_ids:
            record = self.load_patient(pid)
            if not record or not isinstance(record, dict):
                continue

            new_record, truncated = _compact_value(record, max_text, max_bio)
            if truncated > 0:
                updated_count += 1
                if not dry_run:
                    self.save_patient(pid, new_record)
        
        return updated_count
