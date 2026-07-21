import json
import os
from typing import Dict, Any, Optional, List, Set, Tuple
from .repository import PatientRepository

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEGACY_DB_PATH = os.path.join(PROJECT_ROOT, "core", "patients_db.json")

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
    """Local JSON file implementation of PatientRepository."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            self.db_path = os.path.join(os.path.dirname(__file__), "patients_db.json")
        else:
            self.db_path = db_path

    def _migrate_legacy_db(self) -> bool:
        """Migrate legacy patient DB from project_root/core into src/core if present."""
        if not os.path.exists(LEGACY_DB_PATH):
            return False
        try:
            with open(LEGACY_DB_PATH, "r", encoding="utf-8") as f:
                legacy_data = json.load(f)
            if not isinstance(legacy_data, dict) or not legacy_data:
                return False
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(legacy_data, f, indent=2)
            print(f"   🔁 Migrated legacy patient DB to {self.db_path}")
            return True
        except Exception as e:
            # Let it propagate if strict mode expects to see it
            raise RuntimeError(f"Failed to migrate legacy patient DB: {e}")

    def _init_db(self):
        if not os.path.exists(self.db_path):
            if self._migrate_legacy_db():
                return
            try:
                with open(self.db_path, "w", encoding="utf-8") as f:
                    json.dump({}, f)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize JSON DB: {e}")
            return

        # If DB exists but is empty/invalid, attempt migration
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                current = json.load(f)
            if isinstance(current, dict) and not current:
                if self._migrate_legacy_db():
                    return
        except (json.JSONDecodeError, ValueError) as e:
            if self._migrate_legacy_db():
                return
            print(f"   ⚠️  Warning: JSON DB was corrupted. Reinitializing...")
            try:
                with open(self.db_path, "w", encoding="utf-8") as f:
                    json.dump({}, f)
            except Exception as ex:
                raise RuntimeError(f"Failed to reinitialize JSON DB after corruption: {ex}") from e

    def load_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        self._init_db()
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"   ⚠️  Warning: patients_db.json was corrupted. Reinitializing...")
            try:
                with open(self.db_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
            except Exception as ex:
                raise RuntimeError(f"Failed to clear corrupted DB file: {ex}") from e
            data = {}
        except Exception as e:
            raise RuntimeError(f"Failed to load patient from JSON DB: {e}")
        
        key = str(patient_id)
        return data.get(key)

    def save_patient(self, patient_id: str, patient_data: Dict[str, Any]) -> None:
        self._init_db()
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                current_db = json.load(f)
        except (json.JSONDecodeError, ValueError):
            current_db = {}
        except Exception as e:
            raise RuntimeError(f"Failed to load JSON DB for saving: {e}")
        
        key = str(patient_id)
        if key not in current_db:
            current_db[key] = {}
        
        current_db[key].update(patient_data)
        
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(current_db, f, indent=2)
        except Exception as e:
            raise RuntimeError(f"Failed to save patient to JSON DB: {e}")
        
        print(f"      💾 Patient {patient_id} ({patient_data.get('name', 'Unknown')}) saved to JSON DB.")

    def get_patient_name(self, patient_id: str) -> Optional[str]:
        p = self.load_patient(patient_id)
        if p:
            # Check custom first_name/last_name or fallback to name
            first = p.get('first_name', '')
            last = p.get('last_name', '')
            if first or last:
                return f"{first} {last}".strip()
            return p.get('name')
        return None

    def get_all_patient_names(self) -> List[str]:
        self._init_db()
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            names = []
            for pid, p_data in data.items():
                fname = p_data.get('first_name', '')
                lname = p_data.get('last_name', '')
                if fname and lname:
                    names.append(f"{fname} {lname}")
                elif p_data.get('name'):
                    names.append(p_data.get('name'))
            return names
        except Exception as e:
            raise RuntimeError(f"Failed to get all patient names from JSON DB: {e}")

    def list_patient_ids(self) -> List[str]:
        self._init_db()
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [str(k) for k in data.keys()]
        except Exception as e:
            raise RuntimeError(f"Failed to list patient IDs from JSON DB: {e}")

    def delete_patient(self, patient_id: str, archive_dir: str | None = None) -> bool:
        self._init_db()
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load JSON DB for deletion: {e}")
        
        key = str(patient_id)
        if key in data:
            if archive_dir:
                archive_path = os.path.join(archive_dir, f"patient_{patient_id}_db.json")
                try:
                    with open(archive_path, "w", encoding="utf-8") as f:
                        json.dump(data[key], f, indent=2)
                except Exception as e:
                    raise RuntimeError(f"Failed to archive patient DB entry: {e}")
                print(f"      ✅ Archived DB entry: {os.path.basename(archive_path)}")
            
            del data[key]
            
            try:
                with open(self.db_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                raise RuntimeError(f"Failed to write DB after deleting patient: {e}")
            print(f"      ✅ Removed from DB: {patient_id}")
            return True
        else:
            print(f"      ℹ️  ID {patient_id} not found in DB.")
            return False

    def reset_database(self) -> None:
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
        except Exception as e:
            raise RuntimeError(f"Failed to reset JSON database: {e}")

    def compact_patients(self, patient_ids: Set[str], max_text: int, max_bio: int, dry_run: bool) -> int:
        self._init_db()
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Could not read JSON database for compaction: {e}")

        if not isinstance(data, dict):
            raise ValueError("Invalid database format: JSON database must be a dictionary.")

        updated_count = 0
        for pid, record in data.items():
            if patient_ids and pid not in patient_ids:
                continue
            if not isinstance(record, dict):
                continue
            new_record, truncated = _compact_value(record, max_text, max_bio)
            if truncated > 0:
                data[pid] = new_record
                updated_count += 1

        if updated_count > 0 and not dry_run:
            try:
                with open(self.db_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                raise RuntimeError(f"Could not write compacted data back to JSON database: {e}")

        return updated_count
