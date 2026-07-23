import os
import shutil
import glob
import json
import datetime
from ..core import patient_db
from ..core.config import (
    OUTPUT_DIR,
    PATIENT_DATA_DIR,
    get_patient_summary_folder,
    get_patient_logs_folder,
    get_patient_records_folder,
    get_patient_archive_folder,
    SUMMARY_DIR,
    DEBUG_DIR,
    get_patient_root,
)
def confirm_action(message: str, force: bool = False) -> bool:
    """Asks user for confirmation, or skips if force=True."""
    if force: return True
    print(f"\n⚠️  WARNING: {message}")
    response = input("   Are you sure? This cannot be undone. (y/n): ").strip().lower()
    return response == 'y'


def _archive_dir_for_patient(patient_id: str) -> str:
    """
    Creates and returns the archive directory path for a specific patient.

    Args:
        patient_id: The ID of the patient.

    Returns:
        The path to the created archive directory.
    """
    archive_dir = get_patient_archive_folder(patient_id)
    os.makedirs(archive_dir, exist_ok=True)
    return archive_dir


def _archive_files_for_patient(files: list[str], patient_id: str, label: str) -> None:
    """
    Moves a list of patient files to the patient's archive directory with a timestamped prefix.

    Args:
        files: A list of file paths to archive.
        patient_id: The ID of the patient.
        label: A descriptive prefix label for the archived files.
    """
    archive_dir = _archive_dir_for_patient(patient_id)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{label}_{timestamp}__"
    for f in files:
        if not os.path.isfile(f):
            continue
        dst = os.path.join(archive_dir, f"{prefix}{os.path.basename(f)}")
        shutil.move(f, dst)


def purge_patient_selective(patient_id: str, targets: list[str], mode: str = "delete", force: bool = False) -> None:
    """
    Clears specific patient data targets (persona, reports, summary, logs, db, records, debug).

    Args:
        patient_id: The ID of the patient to purge.
        targets: A list of items to purge (e.g. ['persona', 'reports']).
        mode: The operation mode, either 'delete' or 'archive'.
        force: If True, bypasses manual confirmation prompts.

    Raises:
        ValueError: If mode is not 'delete' or 'archive'.
    """
    if mode not in {"delete", "archive"}:
        raise ValueError("Invalid purge mode. Use 'delete' or 'archive'.")
    if not targets:
        return
    targets = [t.lower() for t in targets]

    msg = f"This will {mode} data for Patient ID '{patient_id}' -> {', '.join(targets)}."
    if not confirm_action(msg, force=force):
        print("   ❌ Operation Cancelled.")
        return

    print(f"\n   🗑️  Purging Patient {patient_id} ({mode})...")

    p_root = get_patient_root(patient_id)
    p_summary = get_patient_summary_folder(patient_id)

    # Reports
    if "reports" in targets:
        report_files = glob.glob(os.path.join(p_root, f"DOC-{patient_id}-*.pdf"))
        if mode == "archive":
            _archive_files_for_patient(report_files, patient_id, f"{patient_id}_reports")
        else:
            for f in report_files:
                os.remove(f)
                print(f"      ✅ Deleted: {os.path.basename(f)}")

    # Personas
    if "persona" in targets:
        persona_files = glob.glob(os.path.join(p_root, f"{patient_id}-*persona*.pdf"))
        if mode == "archive":
            _archive_files_for_patient(persona_files, patient_id, f"{patient_id}_persona")
        else:
            for f in persona_files:
                os.remove(f)
                print(f"      ✅ Deleted: {os.path.basename(f)}")

    # Summaries
    if "summary" in targets:
        # Search both root (legacy) and dedicated summary folder
        summary_files = glob.glob(os.path.join(p_root, f"Clinical_Summary_Patient_{patient_id}*.pdf"))
        summary_files.extend(glob.glob(os.path.join(p_root, f"Annotator_Summary_Patient_{patient_id}*.pdf")))
        summary_files.extend(glob.glob(os.path.join(p_root, f"Concise_Summary_Patient_{patient_id}*.pdf")))
        if os.path.exists(p_summary):
            summary_files.extend(glob.glob(os.path.join(p_summary, f"Clinical_Summary_Patient_{patient_id}*.pdf")))
            summary_files.extend(glob.glob(os.path.join(p_summary, f"Annotator_Summary_Patient_{patient_id}*.pdf")))
            summary_files.extend(glob.glob(os.path.join(p_summary, f"Concise_Summary_Patient_{patient_id}*.pdf")))
        
        if mode == "archive":
            _archive_files_for_patient(summary_files, patient_id, f"{patient_id}_summary")
        else:
            for f in summary_files:
                try:
                    os.remove(f)
                    print(f"      ✅ Deleted: {os.path.basename(f)}")
                except Exception:
                    pass

    # Logs
    if "logs" in targets:
        logs_dir = get_patient_logs_folder(patient_id)
        if os.path.exists(logs_dir):
            if mode == "archive":
                _archive_files_for_patient(
                    glob.glob(os.path.join(logs_dir, "*")),
                    patient_id,
                    f"{patient_id}_logs",
                )
            else:
                shutil.rmtree(logs_dir)
                print(f"      ✅ Deleted: {logs_dir}/")

    # Debug state
    if "debug" in targets:
        debug_state = os.path.join(DEBUG_DIR, f"patient_state_{patient_id}.json")
        if os.path.exists(debug_state):
            if mode == "archive":
                _archive_files_for_patient([debug_state], patient_id, f"{patient_id}_debug")
            else:
                os.remove(debug_state)
                print(f"      ✅ Deleted: {os.path.basename(debug_state)}")

    # Records
    if "records" in targets:
        record_dir = get_patient_records_folder(patient_id)
        record_file = os.path.join(record_dir, f"{patient_id}-record.txt")
        if os.path.exists(record_file):
            if mode == "archive":
                _archive_files_for_patient([record_file], patient_id, f"{patient_id}_records")
            else:
                os.remove(record_file)
                print(f"      ✅ Deleted: {os.path.basename(record_file)}")

    # DB entry
    if "db" in targets:
        archive_dir = _archive_dir_for_patient(patient_id) if mode == "archive" else None
        patient_db.delete_patient(patient_id, archive_dir=archive_dir)
        try:
            from ..core import name_cache
            name_cache.remove_entries([patient_id])
        except Exception as e:
            print(f"      ⚠️  Could not remove name cache entry: {e}")

    print(f"\n   ✨ Patient {patient_id} Purge Complete.")

def purge_all(force: bool = False) -> None:
    """
    Clears ALL generated data including documents, summaries, personas, logs, DB, and records.

    Args:
        force: If True, bypasses manual confirmation prompts.
    """
    if not confirm_action("This will WIPEOUT ALL logs, documents, summaries, personas, records, and the Patient Database.", force=force):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging ALL Data...")
    
    # 1. Patient Data
    if os.path.exists(PATIENT_DATA_DIR):
        shutil.rmtree(PATIENT_DATA_DIR)
        os.makedirs(PATIENT_DATA_DIR)
        print(f"      ✅ Deleted: {PATIENT_DATA_DIR}/")

    # 5. Patient DB
    try:
        patient_db.reset_database()
        print("      ✅ Reset: Patient Database")
        try:
            from ..core import name_cache
            name_cache.save_cache({})
            print("      ✅ Reset: Name Cache")
        except Exception as e:
            print(f"      ⚠️  Could not reset name cache: {e}")
    except Exception as e:
        print(f"      ⚠️  Could not reset DB: {e}")

    # 2. Additional Folders
    for d in ["logs", "metadata", "archive", "summary"]:
        target_dir = os.path.join(OUTPUT_DIR, d)
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
            print(f"      ✅ Deleted: {target_dir}/")
    
    if os.path.exists(DEBUG_DIR):
        shutil.rmtree(DEBUG_DIR)
        print(f"      ✅ Deleted: {DEBUG_DIR}/")

    print("\n   ✨ Purge Complete.")


def purge_personas(force: bool = False) -> None:
    """
    Clears all patient records from the Patient Database and deletes persona PDF files.

    Args:
        force: If True, bypasses manual confirmation prompts.
    """
    if not confirm_action("This will clear ALL Personas from DB and delete all persona PDFs.", force=force):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging Personas...")

    # 1. DB
    try:
        patient_db.reset_database()
        print("      ✅ Reset: Patient Database")
        try:
            from ..core import name_cache
            name_cache.save_cache({})
            print("      ✅ Reset: Name Cache")
        except Exception as e:
            print(f"      ⚠️  Could not reset name cache: {e}")
    except Exception as e:
        print(f"      ⚠️  Could not reset DB: {e}")

    # 2. Personas Files
    if os.path.exists(PATIENT_DATA_DIR):
        for folder in os.listdir(PATIENT_DATA_DIR):
            p_root = os.path.join(PATIENT_DATA_DIR, folder)
            if os.path.isdir(p_root):
                for f in glob.glob(os.path.join(p_root, "*-persona-*.pdf")):
                    try:
                        os.remove(f)
                        print(f"      ✅ Deleted: {os.path.basename(f)}")
                    except Exception:
                        pass
    
    print("\n   ✨ Personas Purged.")


def purge_documents(force: bool = False) -> None:
    """
    Clears all report PDFs and summary PDFs but preserves patient personas.

    Args:
        force: If True, bypasses manual confirmation prompts.
    """
    if not confirm_action("This will clear ALL Patient Documents (Reports/Summaries) but PRESERVE Personas.", force=force):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging Documents (Preserving Personas)...")
    
    if os.path.exists(PATIENT_DATA_DIR):
        for folder in os.listdir(PATIENT_DATA_DIR):
            p_root = os.path.join(PATIENT_DATA_DIR, folder)
            if os.path.isdir(p_root):
                # Clear reports (DOC-*.pdf)
                for f in glob.glob(os.path.join(p_root, "DOC-*.pdf")):
                    try:
                        os.remove(f)
                    except Exception:
                        pass
                # Clear summaries
                for pattern in ["Clinical_Summary_Patient_*.pdf", "Annotator_Summary_Patient_*.pdf", "Concise_Summary_Patient_*.pdf"]:
                    for f in glob.glob(os.path.join(p_root, pattern)):
                        try:
                            os.remove(f)
                        except Exception:
                            pass
        
        # Also clear dedicated summary folder
        if os.path.exists(SUMMARY_DIR):
            try:
                shutil.rmtree(SUMMARY_DIR)
                os.makedirs(SUMMARY_DIR)
            except Exception:
                pass
            
        print(f"      ✅ Cleared reports + summaries.")
    
    print("\n   ✨ Documents Purged.")


def purge_summaries_only(force: bool = False) -> None:
    """
    Deletes only summary PDFs from the summary/ folder and patient folders.

    Args:
        force: If True, bypasses manual confirmation prompts.
    """
    if not confirm_action("This will delete ALL Summary PDFs but preserve Reports and Personas.", force=force):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging Summaries Only...")
    
    count = 0
    # 1. Clear summary PDFs inside patient folders (legacy)
    if os.path.exists(PATIENT_DATA_DIR):
        for folder in os.listdir(PATIENT_DATA_DIR):
            p_root = os.path.join(PATIENT_DATA_DIR, folder)
            if os.path.isdir(p_root):
                for pattern in ["Clinical_Summary_Patient_*.pdf", "Annotator_Summary_Patient_*.pdf", "Concise_Summary_Patient_*.pdf"]:
                    for f in glob.glob(os.path.join(p_root, pattern)):
                        try:
                            os.remove(f)
                            count += 1
                            print(f"      ✅ Deleted (legacy): {os.path.basename(f)}")
                        except Exception:
                            pass
    
    # 2. Clear dedicated summary folder
    if os.path.exists(SUMMARY_DIR):
        try:
            shutil.rmtree(SUMMARY_DIR)
            os.makedirs(SUMMARY_DIR)
            print(f"      ✅ Wiped dedicated summary folder: {SUMMARY_DIR}/")
        except Exception:
            pass
    
    print(f"\n   ✨ Deleted {count} summary file(s).")


def purge_reports_only(force: bool = False) -> None:
    """
    Deletes only report PDFs (DOC-*.pdf) for all patients, preserving summaries and personas.

    Args:
        force: If True, bypasses manual confirmation prompts.
    """
    if not confirm_action("This will delete ALL Report PDFs but preserve Summaries and Personas.", force=force):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging Reports Only...")
    
    count = 0
    if os.path.exists(PATIENT_DATA_DIR):
        for folder in os.listdir(PATIENT_DATA_DIR):
            p_root = os.path.join(PATIENT_DATA_DIR, folder)
            if os.path.isdir(p_root):
                report_files = glob.glob(os.path.join(p_root, "DOC-*.pdf"))
                for f in report_files:
                    try:
                        os.remove(f)
                        count += 1
                        print(f"      ✅ Deleted: {os.path.basename(f)}")
                    except Exception:
                        pass
    
    print(f"\n   ✨ Deleted {count} report file(s).")


def purge_reports_and_summaries(force: bool = False) -> None:
    """
    Deletes both report and summary PDFs, preserving patient personas.

    Args:
        force: If True, bypasses manual confirmation prompts.
    """
    if not confirm_action("This will delete ALL Reports and Summaries but preserve Personas.", force=force):
        print("   ❌ Operation Cancelled.")
        return

    print("\n   🗑️  Purging Reports and Summaries...")
    
    if os.path.exists(PATIENT_DATA_DIR):
        for folder in os.listdir(PATIENT_DATA_DIR):
            p_root = os.path.join(PATIENT_DATA_DIR, folder)
            if os.path.isdir(p_root):
                # Clear reports
                for f in glob.glob(os.path.join(p_root, "DOC-*.pdf")):
                    try:
                        os.remove(f)
                    except Exception:
                        pass
                # Clear summaries
                for pattern in ["Clinical_Summary_Patient_*.pdf", "Annotator_Summary_Patient_*.pdf", "Concise_Summary_Patient_*.pdf"]:
                    for f in glob.glob(os.path.join(p_root, pattern)):
                        try:
                            os.remove(f)
                        except Exception:
                            pass
        
        # Also clear dedicated summary folder
        if os.path.exists(SUMMARY_DIR):
            try:
                shutil.rmtree(SUMMARY_DIR)
                os.makedirs(SUMMARY_DIR)
            except Exception:
                pass
            
        print(f"      ✅ Deleted: reports + summaries.")
    
    print("\n   ✨ Reports and Summaries Purged.")


def purge_patient(patient_id: str, force: bool = False) -> None:
    """
    Clears all generated data files and DB record for a specific patient.

    Args:
        patient_id: The ID of the patient to purge.
        force: If True, bypasses manual confirmation prompts.
    """
    default_targets = ["persona", "reports", "summary", "logs", "db", "records", "debug"]
    purge_patient_selective(patient_id, default_targets, mode="delete", force=force)
