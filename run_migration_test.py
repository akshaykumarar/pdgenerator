import os
import tempfile
from dotenv import load_dotenv

print("1. Loading dotenv...")
load_dotenv("cred/.env")

print(f"DB_HOST is: {os.getenv('DB_HOST')}")

print("2. Importing migration functions...")
from migrate_json_to_postgres import migrate as migrate_to_pg
from migrate_postgres_to_json import migrate as migrate_to_json
from src.core.json_repository import JSONPatientRepository
from src.core.postgres_repository import PostgresPatientRepository

print("3. Creating temp JSON db...")
fd, temp_json_path = tempfile.mkstemp(suffix=".json")
os.close(fd)

print(f"Temp JSON path: {temp_json_path}")

try:
    os.environ["DB_SCHEMA"] = "pdgenerator_migration_test"
    
    print("4. Initializing JSON repository...")
    dest_json_repo = JSONPatientRepository(temp_json_path)
    dest_json_repo._init_db()
    
    print("5. Initializing PostgreSQL repository...")
    postgres_repo = PostgresPatientRepository()
    postgres_repo._init_db()
    
    print("6. Resetting PostgreSQL database...")
    postgres_repo.reset_database()
    
    print("7. Adding sample patient to JSON...")
    sample_patient = {
        "first_name": "Migration",
        "last_name": "Test",
        "gender": "male",
        "dob": "1999-09-09",
        "bio_narrative": "Patient for migration testing.",
        "diagnoses": []
    }
    dest_json_repo.save_patient("999", sample_patient)
    
    print("8. Migrating JSON to Postgres...")
    migrate_to_pg(strategy="update", json_path=temp_json_path)
    
    print("9. Verifying load from Postgres...")
    loaded_pg = postgres_repo.load_patient("999")
    print(f"Loaded from PG: {loaded_pg}")
    
    print("10. Modifying in Postgres...")
    sample_patient_modified = loaded_pg.copy()
    sample_patient_modified["first_name"] = "MigrationModified"
    postgres_repo.save_patient("999", sample_patient_modified)
    
    print("11. Deleting from JSON...")
    dest_json_repo.delete_patient("999")
    
    print("12. Reverse migrating Postgres to JSON...")
    migrate_to_json(strategy="update", json_path=temp_json_path)
    
    print("13. Verifying load from JSON...")
    loaded_json = dest_json_repo.load_patient("999")
    print(f"Loaded from JSON: {loaded_json}")
    
    print("14. Modifying in JSON for conflict test...")
    loaded_json["first_name"] = "ConflictJSON"
    dest_json_repo.save_patient("999", loaded_json)
    
    print("15. Migrating with skip strategy...")
    migrate_to_pg(strategy="skip", json_path=temp_json_path)
    print(f"Postgres name (should be MigrationModified): {postgres_repo.load_patient('999')['first_name']}")
    
    print("16. Migrating with fail strategy...")
    try:
        migrate_to_pg(strategy="fail", json_path=temp_json_path)
        print("❌ Fail strategy did not raise error")
    except Exception as e:
        print(f"✅ Fail strategy correctly raised: {type(e).__name__}: {e}")
        
    print("17. Migrating with update strategy...")
    migrate_to_pg(strategy="update", json_path=temp_json_path)
    print(f"Postgres name (should be ConflictJSON): {postgres_repo.load_patient('999')['first_name']}")
    
finally:
    print("🧹 Cleaning up...")
    if os.path.exists(temp_json_path):
        os.remove(temp_json_path)
    try:
        conn = postgres_repo._connect()
        with conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {postgres_repo.schema} CASCADE;")
        conn.commit()
        conn.close()
        print("Schema dropped successfully.")
    except Exception as ex:
        print(f"Error dropping schema: {ex}")
    print("Finished.")
