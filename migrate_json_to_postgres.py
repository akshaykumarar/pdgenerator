#!/usr/bin/env python3
"""
Migration utility to migrate patient records from Local JSON database to PostgreSQL.
Supports skip/update/fail conflict resolution strategies.
"""

import argparse
import sys
import os
from typing import Optional

# Setup path and imports
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(PROJECT_ROOT, "cred", ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
except ImportError:
    pass

try:
    from core.json_repository import JSONPatientRepository
    from core.postgres_repository import PostgresPatientRepository
except ImportError as e:
    print(f"❌ Critical Error: Could not import core components ({e})", file=sys.stderr)
    print("   Please ensure you are running this from the project root within the virtual environment.", file=sys.stderr)
    sys.exit(1)


def migrate(strategy: str, json_path: Optional[str] = None) -> None:
    """
    Migrates patient records from JSON to PostgreSQL database.

    Args:
        strategy: Conflict resolution strategy ('skip', 'update', 'fail').
        json_path: Optional path to custom patients_db.json file.
    
    Raises:
        ValueError: If an invalid strategy is specified.
        RuntimeError: If a conflict occurs and 'fail' strategy is active.
    """
    if strategy not in ("skip", "update", "fail"):
        raise ValueError(f"Invalid strategy '{strategy}'. Must be 'skip', 'update', or 'fail'.")

    # 1. Resolve JSON database path
    if json_path is None:
        json_path = os.path.join(PROJECT_ROOT, "src", "core", "patients_db.json")

    if not os.path.exists(json_path):
        print(f"❌ Source JSON DB path not found: {json_path}")
        sys.exit(1)

    # 2. Instantiate repositories
    print(f"🔌 Connecting to storage backends...")
    json_repo = JSONPatientRepository(json_path)
    json_repo._init_db()

    postgres_repo = PostgresPatientRepository()
    postgres_repo._init_db()

    # 3. Load source records
    json_ids = json_repo.list_patient_ids()
    if not json_ids:
        print("ℹ️ Source JSON database is empty. Nothing to migrate.")
        return

    print(f"📦 Found {len(json_ids)} patient records in JSON database.")

    # 4. Check for conflicts
    postgres_ids = postgres_repo.list_patient_ids()
    conflicts = set(json_ids).intersection(set(postgres_ids))

    if conflicts:
        print(f"⚠️ Found {len(conflicts)} conflicting patient ID(s) in the destination database.")
        if strategy == "fail":
            raise RuntimeError(
                f"Migration aborted due to existing patient ID conflicts in destination: {sorted(list(conflicts))}"
            )

    # 5. Perform migration
    migrated_count = 0
    skipped_count = 0
    updated_count = 0

    for pid in json_ids:
        patient_data = json_repo.load_patient(pid)
        if not patient_data:
            continue

        if pid in conflicts:
            if strategy == "skip":
                print(f"⏭️ [SKIP] Patient {pid} already exists in PostgreSQL.")
                skipped_count += 1
                continue
            elif strategy == "update":
                print(f"🔄 [UPDATE] Overwriting patient {pid} in PostgreSQL.")
                postgres_repo.save_patient(pid, patient_data)
                updated_count += 1
                migrated_count += 1
        else:
            print(f"📥 [INSERT] Migrating patient {pid} to PostgreSQL.")
            postgres_repo.save_patient(pid, patient_data)
            migrated_count += 1

    print(f"\n✨ JSON to PostgreSQL migration complete!")
    print(f"   - Total processed: {migrated_count + skipped_count}")
    print(f"   - Migrated (new/updated): {migrated_count} (New: {migrated_count - updated_count}, Updated: {updated_count})")
    print(f"   - Skipped: {skipped_count}")


def main() -> None:
    """CLI entry point for JSON -> PostgreSQL migration."""
    parser = argparse.ArgumentParser(description="Migrate local JSON patient database to PostgreSQL.")
    parser.add_argument(
        "--strategy",
        choices=["skip", "update", "fail"],
        default="update",
        help="Strategy to handle duplicate/conflicting patient IDs. Default: 'update'."
    )
    parser.add_argument(
        "--json-path",
        help="Path to custom patients_db.json file. Default: src/core/patients_db.json."
    )
    args = parser.parse_args()

    try:
        migrate(strategy=args.strategy, json_path=args.json_path)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
