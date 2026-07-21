import os
from typing import Dict, Any, Optional, List, Set
from .repository import PatientRepository

class PostgresPatientRepository(PatientRepository):
    """PostgreSQL repository implementation using psycopg2."""

    def __init__(self):
        # Cache schema name, defaults to 'pdgenerator'
        self.schema = os.getenv("DB_SCHEMA", "pdgenerator").strip()

    def _connect(self):
        import psycopg2
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        database = os.getenv("DB_NAME", "neondb")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "")
        sslmode = os.getenv("DB_SSL_MODE", "require")
        channel_binding = os.getenv("DB_CHANNEL_BINDING", "require")
        
        try:
            return psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                sslmode=sslmode,
                channel_binding=channel_binding
            )
        except Exception as e:
            raise RuntimeError(f"PostgreSQL Connection Error: {e}")

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema};")
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema}.patients (
                        patient_id VARCHAR(50) PRIMARY KEY,
                        first_name VARCHAR(100) NOT NULL,
                        last_name VARCHAR(100) NOT NULL,
                        dob DATE,
                        gender VARCHAR(50),
                        persona_data JSONB NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_patients_name ON {self.schema}.patients(last_name, first_name);")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_patients_dob ON {self.schema}.patients(dob);")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_patients_persona_gin ON {self.schema}.patients USING gin(persona_data);")
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"PostgreSQL Database Initialization Error: {e}")
        finally:
            conn.close()

    def load_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        self._init_db()
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT persona_data FROM {self.schema}.patients WHERE patient_id = %s;",
                    (str(patient_id),)
                )
                row = cur.fetchone()
                if row:
                    return row[0]
                return None
        except Exception as e:
            raise RuntimeError(f"PostgreSQL Load Patient Error: {e}")
        finally:
            conn.close()

    def save_patient(self, patient_id: str, patient_data: Dict[str, Any]) -> None:
        self._init_db()
        
        # Merge if exists
        existing = self.load_patient(patient_id) or {}
        existing.update(patient_data)
        
        first_name = existing.get("first_name", "").strip()
        last_name = existing.get("last_name", "").strip()
        dob_str = existing.get("dob")
        gender = existing.get("gender")
        
        # Parse date if available
        import datetime
        dob = None
        if dob_str:
            for fmt in ("%Y-%m-%d", "%m-%d-%Y"):
                try:
                    dob = datetime.datetime.strptime(dob_str, fmt).date()
                    break
                except ValueError:
                    pass
        
        conn = self._connect()
        try:
            import psycopg2.extras
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.schema}.patients (patient_id, first_name, last_name, dob, gender, persona_data, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (patient_id) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        dob = EXCLUDED.dob,
                        gender = EXCLUDED.gender,
                        persona_data = EXCLUDED.persona_data,
                        updated_at = CURRENT_TIMESTAMP;
                """, (
                    str(patient_id),
                    first_name,
                    last_name,
                    dob,
                    gender,
                    psycopg2.extras.Json(existing)
                ))
            conn.commit()
            print(f"      💾 Patient {patient_id} ({first_name} {last_name}) saved to PostgreSQL DB.")
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"PostgreSQL Save Patient Error: {e}")
        finally:
            conn.close()

    def get_patient_name(self, patient_id: str) -> Optional[str]:
        self._init_db()
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT first_name, last_name, persona_data FROM {self.schema}.patients WHERE patient_id = %s;",
                    (str(patient_id),)
                )
                row = cur.fetchone()
                if row:
                    first, last, persona = row
                    if first or last:
                        return f"{first} {last}".strip()
                    if persona:
                        return persona.get("name")
                return None
        except Exception as e:
            raise RuntimeError(f"PostgreSQL Get Patient Name Error: {e}")
        finally:
            conn.close()

    def get_all_patient_names(self) -> List[str]:
        self._init_db()
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT first_name, last_name, persona_data FROM {self.schema}.patients;")
                rows = cur.fetchall()
                names = []
                for row in rows:
                    first, last, persona = row
                    if first or last:
                        names.append(f"{first} {last}".strip())
                    elif persona and persona.get("name"):
                        names.append(persona.get("name"))
                return names
        except Exception as e:
            raise RuntimeError(f"PostgreSQL Get All Patient Names Error: {e}")
        finally:
            conn.close()

    def list_patient_ids(self) -> List[str]:
        self._init_db()
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT patient_id FROM {self.schema}.patients;")
                rows = cur.fetchall()
                return [str(row[0]) for row in rows]
        except Exception as e:
            raise RuntimeError(f"PostgreSQL List Patient IDs Error: {e}")
        finally:
            conn.close()

    def delete_patient(self, patient_id: str, archive_dir: str | None = None) -> bool:
        self._init_db()
        
        # Load first if we need to archive
        existing = None
        if archive_dir:
            existing = self.load_patient(patient_id)
            
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self.schema}.patients WHERE patient_id = %s RETURNING patient_id;",
                    (str(patient_id),)
                )
                row = cur.fetchone()
                deleted = row is not None
            conn.commit()
            
            if deleted:
                if archive_dir and existing:
                    import json
                    archive_path = os.path.join(archive_dir, f"patient_{patient_id}_db.json")
                    with open(archive_path, "w", encoding="utf-8") as f:
                        json.dump(existing, f, indent=2)
                    print(f"      ✅ Archived DB entry: {os.path.basename(archive_path)}")
                print(f"      ✅ Removed from DB: {patient_id}")
                return True
            else:
                print(f"      ℹ️  ID {patient_id} not found in DB.")
                return False
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"PostgreSQL Delete Patient Error: {e}")
        finally:
            conn.close()

    def reset_database(self) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE TABLE {self.schema}.patients;")
            conn.commit()
            print("      ✅ Reset: PostgreSQL Database Table")
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"PostgreSQL Reset Database Error: {e}")
        finally:
            conn.close()

    def compact_patients(self, patient_ids: Set[str], max_text: int, max_bio: int, dry_run: bool) -> int:
        self._init_db()
        conn = self._connect()
        try:
            import json
            import psycopg2.extras
            with conn.cursor() as cur:
                if patient_ids:
                    # Parameterized query with tuple
                    # Check if tuple is singular to avoid syntax errors
                    p_ids_tuple = tuple(str(pid) for pid in patient_ids)
                    if len(p_ids_tuple) == 1:
                        cur.execute(
                            f"SELECT patient_id, persona_data FROM {self.schema}.patients WHERE patient_id = %s;",
                            (p_ids_tuple[0],)
                        )
                    else:
                        cur.execute(
                            f"SELECT patient_id, persona_data FROM {self.schema}.patients WHERE patient_id IN %s;",
                            (p_ids_tuple,)
                        )
                else:
                    cur.execute(f"SELECT patient_id, persona_data FROM {self.schema}.patients;")
                rows = cur.fetchall()
            
            updated_count = 0
            from .json_repository import _compact_value
            
            with conn.cursor() as cur:
                for pid, record in rows:
                    if not isinstance(record, dict):
                        continue
                    new_record, truncated = _compact_value(record, max_text, max_bio)
                    if truncated > 0:
                        updated_count += 1
                        if not dry_run:
                            first_name = new_record.get("first_name", "").strip()
                            last_name = new_record.get("last_name", "").strip()
                            dob_str = new_record.get("dob")
                            gender = new_record.get("gender")
                            
                            import datetime
                            dob = None
                            if dob_str:
                                for fmt in ("%Y-%m-%d", "%m-%d-%Y"):
                                    try:
                                        dob = datetime.datetime.strptime(dob_str, fmt).date()
                                        break
                                    except ValueError:
                                        pass
                                        
                            cur.execute(f"""
                                UPDATE {self.schema}.patients SET
                                    first_name = %s,
                                    last_name = %s,
                                    dob = %s,
                                    gender = %s,
                                    persona_data = %s,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE patient_id = %s;
                            """, (first_name, last_name, dob, gender, psycopg2.extras.Json(new_record), str(pid)))
            conn.commit()
            return updated_count
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"PostgreSQL Compact Patients Error: {e}")
        finally:
            conn.close()
