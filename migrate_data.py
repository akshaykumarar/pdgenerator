#!/usr/bin/env python3
"""
Unified Migration Utility for Clinical Data Generator.
Supports bidirectional migration (JSON -> PostgreSQL and PostgreSQL -> JSON)
across Patients, Insurance Providers & Plans, and CPT Code Mappings.

Usage examples:
  python migrate_data.py --direction json_to_db --entities all --strategy update
  python migrate_data.py --direction db_to_json --entities all --strategy update
  python migrate_data.py --direction json_to_db --entities insurance,cpt
"""

import argparse
import sys
import os
from typing import Optional, List

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
    from core import insurance_config
    from data import loader
except ImportError as e:
    print(f"❌ Critical Error: Could not import core components ({e})", file=sys.stderr)
    print("   Please run within the virtual environment from the project root.", file=sys.stderr)
    sys.exit(1)


def migrate_patients(direction: str, strategy: str, json_path: Optional[str] = None) -> None:
    """Migrate patient records between JSON and PostgreSQL."""
    if json_path is None:
        json_path = os.path.join(PROJECT_ROOT, "src", "core", "patients_db.json")

    json_repo = JSONPatientRepository(json_path)
    json_repo._init_db()

    postgres_repo = PostgresPatientRepository()
    postgres_repo._init_db()

    if direction == "json_to_db":
        src_repo, dst_repo = json_repo, postgres_repo
        src_label, dst_label = "JSON DB", "PostgreSQL"
    else:
        src_repo, dst_repo = postgres_repo, json_repo
        src_label, dst_label = "PostgreSQL", "JSON DB"

    src_ids = src_repo.list_patient_ids()
    if not src_ids:
        print(f"ℹ️ Source {src_label} patient database is empty. Nothing to migrate for patients.")
        return

    print(f"📦 [Patients] Found {len(src_ids)} patient records in {src_label}.")

    dst_ids = dst_repo.list_patient_ids()
    conflicts = set(src_ids).intersection(set(dst_ids))

    if conflicts and strategy == "fail":
        raise RuntimeError(f"Patient migration aborted due to conflicts: {sorted(list(conflicts))}")

    migrated, skipped, updated = 0, 0, 0
    for pid in src_ids:
        patient_data = src_repo.load_patient(pid)
        if not patient_data:
            continue

        if pid in conflicts:
            if strategy == "skip":
                print(f"  ⏭️ [SKIP] Patient {pid} already exists in {dst_label}.")
                skipped += 1
                continue
            elif strategy == "update":
                print(f"  🔄 [UPDATE] Overwriting patient {pid} in {dst_label}.")
                dst_repo.save_patient(pid, patient_data)
                updated += 1
                migrated += 1
        else:
            print(f"  📥 [INSERT] Migrating patient {pid} to {dst_label}.")
            dst_repo.save_patient(pid, patient_data)
            migrated += 1

    print(f"✨ Patient migration ({src_label} -> {dst_label}) complete!")
    print(f"   Migrated: {migrated} (New: {migrated - updated}, Updated: {updated}), Skipped: {skipped}\n")


def migrate_insurance(direction: str, strategy: str) -> None:
    """Migrate Insurance Providers & Plans between JSON and PostgreSQL."""
    postgres_repo = PostgresPatientRepository()
    postgres_repo._init_db()

    if direction == "json_to_db":
        file_cfg = insurance_config._load_config_from_file()
        if not file_cfg or not file_cfg.get("providers"):
            print("ℹ️ Source core/insurance_config.json is empty. Skipping insurance migration.")
            return

        print("📦 [Insurance] Migrating providers & plans from JSON -> PostgreSQL...")
        postgres_repo.save_insurance_config(file_cfg)
        print("✨ Insurance config migration (JSON -> PostgreSQL) complete!\n")

    else:
        db_cfg = postgres_repo.load_insurance_config()
        if not db_cfg or not db_cfg.get("providers"):
            print("ℹ️ Source PostgreSQL insurance tables are empty. Skipping insurance migration.")
            return

        print("📦 [Insurance] Exporting providers & plans from PostgreSQL -> core/insurance_config.json...")
        json_file_path = os.path.join(PROJECT_ROOT, "core", "insurance_config.json")
        import json
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(db_cfg, f, indent=2)
        print("✨ Insurance config export (PostgreSQL -> JSON) complete!\n")


def migrate_cpt(direction: str, strategy: str) -> None:
    """Migrate CPT / HCPCS Code Mappings between JSON and PostgreSQL."""
    postgres_repo = PostgresPatientRepository()
    postgres_repo._init_db()

    cpt_json_path = os.path.join(PROJECT_ROOT, "core", "cpt_code_map.json")

    if direction == "json_to_db":
        if not os.path.exists(cpt_json_path):
            print("ℹ️ Source core/cpt_code_map.json not found. Skipping CPT migration.")
            return

        import json
        with open(cpt_json_path, "r", encoding="utf-8") as f:
            cpt_map = json.load(f)

        print(f"📦 [CPT Mappings] Migrating {len(cpt_map.get('by_code', {}))} CPT codes from JSON -> PostgreSQL...")
        postgres_repo.save_cpt_code_map(cpt_map)
        print("✨ CPT code mapping migration (JSON -> PostgreSQL) complete!\n")

    else:
        db_map = postgres_repo.load_cpt_code_map()
        if not db_map or not db_map.get("by_code"):
            print("ℹ️ Source PostgreSQL cpt_code_map table is empty. Skipping CPT migration.")
            return

        print(f"📦 [CPT Mappings] Exporting {len(db_map.get('by_code', {}))} CPT codes from PostgreSQL -> JSON...")
        import json
        with open(cpt_json_path, "w", encoding="utf-8") as f:
            json.dump(db_map, f, indent=2)
        print("✨ CPT code mapping export (PostgreSQL -> JSON) complete!\n")


def migrate(direction: str = "json_to_db", entity: str = "all", strategy: str = "update", json_path: Optional[str] = None) -> None:
    """Programmatic entry point for migrating data between JSON and PostgreSQL."""
    target_entities = [e.strip().lower() for e in entity.split(",")]
    if "all" in target_entities:
        target_entities = ["patients", "insurance", "cpt"]

    if "patients" in target_entities:
        migrate_patients(direction, strategy, json_path)
    if "insurance" in target_entities:
        migrate_insurance(direction, strategy)
    if "cpt" in target_entities:
        migrate_cpt(direction, strategy)


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified bidirectional migration tool for Clinical Data Generator.")
    parser.add_argument(
        "--direction",
        choices=["json_to_db", "db_to_json"],
        default="json_to_db",
        help="Direction of migration. Default: 'json_to_db'."
    )
    parser.add_argument(
        "--entities",
        default="all",
        help="Comma-separated list of entities to migrate: 'all', 'patients', 'insurance', 'cpt'. Default: 'all'."
    )
    parser.add_argument(
        "--strategy",
        choices=["skip", "update", "fail"],
        default="update",
        help="Conflict resolution strategy for patient records. Default: 'update'."
    )
    parser.add_argument(
        "--json-path",
        help="Custom path to patients_db.json file."
    )
    args = parser.parse_args()

    print(f"\n🚀 Starting Unified Data Migration ({args.direction.upper()})")
    print(f"   Target Entities: {args.entities}")
    print(f"   Conflict Strategy: {args.strategy}\n")

    try:
        migrate(direction=args.direction, entity=args.entities, strategy=args.strategy, json_path=args.json_path)
        print("🎉 Unified migration finished successfully!\n")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
