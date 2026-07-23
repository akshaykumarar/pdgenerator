"""
src/core/name_cache.py
----------------------
Thread-safe local file cache for patient ID → display name mappings.

Cache file: core/patient_name_cache.json
Format   : {"names": {"110": "John Smith", "111": "Jane Doe", ...}}

Why this exists
---------------
/api/patients must return the patient list fast enough for the UI dropdown to
populate on page load.  Querying PostgreSQL per-patient (or even in bulk) adds
network latency.  This cache lets the response return instantly from disk; a
background thread then refreshes names from the DB and writes back, so the
next page load sees up-to-date names.
"""
import os
import json
import threading
from typing import Dict

# Resolve path: src/core/ → src/ → project root → core/
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
CACHE_PATH = os.path.join(_PROJECT_ROOT, "core", "patient_name_cache.json")

_lock = threading.Lock()


def load_cache() -> Dict[str, str]:
    """
    Read the name cache from disk.

    Returns:
        Dict mapping patient_id (str) → display name (str).
        Returns an empty dict if the file is missing or corrupt.
    """
    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("names", {})
    except Exception:
        pass
    return {}


def save_cache(names: Dict[str, str]) -> None:
    """
    Persist the complete name dict to disk (thread-safe, atomic-ish via write).

    Args:
        names: Full {patient_id: display_name} mapping to persist.
    """
    with _lock:
        try:
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump({"names": names}, f, indent=2)
        except Exception as e:
            print(f"[WARNING] name_cache: Failed to save cache: {e}")


def update_entry(patient_id: str, name: str) -> None:
    """
    Update a single patient entry in the cache (read-modify-write, thread-safe).
    Call this whenever a patient persona is saved so names stay fresh immediately.

    Args:
        patient_id: Numeric string patient ID.
        name:       Display name e.g. "John Smith".
    """
    with _lock:
        current: Dict[str, str] = {}
        try:
            if os.path.exists(CACHE_PATH):
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    current = json.load(f).get("names", {})
        except Exception:
            pass
        current[patient_id] = name
        try:
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump({"names": current}, f, indent=2)
        except Exception as e:
            print(f"[WARNING] name_cache: Failed to update entry for {patient_id}: {e}")


def remove_entries(patient_ids: list[str]) -> None:
    """
    Remove patient entries from the cache (read-modify-write, thread-safe).
    Call this whenever patients are purged so they are removed from the cache.

    Args:
        patient_ids: List of numeric string patient IDs to remove.
    """
    with _lock:
        current: Dict[str, str] = {}
        try:
            if os.path.exists(CACHE_PATH):
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    current = json.load(f).get("names", {})
        except Exception:
            pass
        for pid in patient_ids:
            current.pop(pid, None)
        try:
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump({"names": current}, f, indent=2)
        except Exception as e:
            print(f"[WARNING] name_cache: Failed to remove entries: {e}")

