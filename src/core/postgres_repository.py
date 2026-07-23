import os
import re
import datetime
from typing import Dict, Any, Optional, List, Set
from .repository import PatientRepository

# Valid PostgreSQL identifier: starts with letter or underscore, alphanumeric/underscore only
_SCHEMA_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

class PostgresPatientRepository(PatientRepository):
    """PostgreSQL repository implementation using psycopg2."""

    def __init__(self) -> None:
        """Initializes the PostgreSQL repository, caching database schema configuration."""
        # Cache schema name, defaults to 'pdgenerator'
        self.schema = os.getenv("DB_SCHEMA", "pdgenerator").strip()
        if not _SCHEMA_NAME_RE.match(self.schema):
            raise ValueError(
                f"Invalid DB_SCHEMA value '{self.schema}'. "
                "Schema names must match ^[a-zA-Z_][a-zA-Z0-9_]*$ to prevent SQL injection."
            )
        # Guard flag: DDL is executed only once per repository instance
        self._schema_initialized = False

    def _connect(self) -> Any:
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
        if self._schema_initialized:
            return
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema};")
                
                # 1. Patients Table
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

                # 2. Insurance Providers Table
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema}.insurance_providers (
                        provider_id VARCHAR(50) PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        abbreviation VARCHAR(50),
                        policy_url TEXT,
                        is_default BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 3. Insurance Plans Table
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema}.insurance_plans (
                        plan_id VARCHAR(100) PRIMARY KEY,
                        provider_id VARCHAR(50) NOT NULL REFERENCES {self.schema}.insurance_providers(provider_id) ON DELETE CASCADE,
                        plan_name VARCHAR(255) NOT NULL,
                        plan_type VARCHAR(100) NOT NULL,
                        policy_url TEXT,
                        is_default BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_insurance_plans_provider ON {self.schema}.insurance_plans(provider_id);")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_insurance_plans_type ON {self.schema}.insurance_plans(plan_type);")

                # 4. CPT / HCPCS Code Mapping Table
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema}.cpt_code_map (
                        cpt_code VARCHAR(50) PRIMARY KEY,
                        procedure_name TEXT NOT NULL,
                        department VARCHAR(100),
                        test_case VARCHAR(100),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_cpt_procedure_lower ON {self.schema}.cpt_code_map (LOWER(procedure_name));")
            conn.commit()
            self._schema_initialized = True
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
        existing = self.load_patient(patient_id) or {}
        existing.update(patient_data)
        
        first_name = existing.get("first_name", "").strip()
        last_name = existing.get("last_name", "").strip()
        dob_str = existing.get("dob")
        gender = existing.get("gender")
        
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

    def get_patient_names_bulk(self, patient_ids: List[str]) -> Dict[str, str]:
        """
        Fetch first_name + last_name for a list of IDs in a single query.
        Returns {patient_id: 'First Last'} for IDs that exist in the DB.
        IDs not found are omitted (caller should fall back to 'Patient {id}').
        """
        if not patient_ids:
            return {}
        self._init_db()
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT patient_id, first_name, last_name, persona_data
                    FROM {self.schema}.patients
                    WHERE patient_id = ANY(%s);
                    """,
                    (patient_ids,)
                )
                rows = cur.fetchall()
            result: Dict[str, str] = {}
            for pid, first, last, persona in rows:
                if first or last:
                    result[str(pid)] = f"{first} {last}".strip()
                elif persona and persona.get("name"):
                    result[str(pid)] = persona.get("name")
            return result
        except Exception as e:
            raise RuntimeError(f"PostgreSQL Bulk Get Patient Names Error: {e}")
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
                cur.execute(f"TRUNCATE TABLE {self.schema}.insurance_plans CASCADE;")
                cur.execute(f"TRUNCATE TABLE {self.schema}.insurance_providers CASCADE;")
                cur.execute(f"TRUNCATE TABLE {self.schema}.cpt_code_map;")
            conn.commit()
            print("      ✅ Reset: PostgreSQL Database Tables")
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"PostgreSQL Reset Database Error: {e}")
        finally:
            conn.close()

    def compact_patients(self, patient_ids: Set[str], max_text: int, max_bio: int, dry_run: bool) -> int:
        self._init_db()
        conn = self._connect()
        try:
            import psycopg2.extras
            with conn.cursor() as cur:
                if patient_ids:
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

    # ── Insurance Providers & Plans Methods ──────────────────────────
    def load_insurance_config(self) -> Dict[str, Any]:
        self._init_db()
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT provider_id, name, abbreviation, policy_url, is_default FROM {self.schema}.insurance_providers ORDER BY provider_id;")
                provider_rows = cur.fetchall()
                if not provider_rows:
                    return {"default_provider_id": None, "providers": []}

                cur.execute(f"SELECT plan_id, provider_id, plan_name, plan_type, policy_url, is_default FROM {self.schema}.insurance_plans ORDER BY plan_id;")
                plan_rows = cur.fetchall()

            plans_by_provider: Dict[str, List[Dict[str, Any]]] = {}
            for pid, prov_id, pname, ptype, purl, is_def in plan_rows:
                if prov_id not in plans_by_provider:
                    plans_by_provider[prov_id] = []
                plans_by_provider[prov_id].append({
                    "plan_id": pid,
                    "plan_name": pname,
                    "plan_type": ptype,
                    "policy_url": purl or "",
                    "is_default": bool(is_def)
                })

            providers = []
            default_provider_id = None
            for prov_id, pname, abbrev, purl, is_def in provider_rows:
                if is_def:
                    default_provider_id = prov_id
                providers.append({
                    "provider_id": prov_id,
                    "name": pname,
                    "abbreviation": abbrev or "",
                    "policy_url": purl or "",
                    "plans": plans_by_provider.get(prov_id, [])
                })
            if not default_provider_id and providers:
                default_provider_id = providers[0]["provider_id"]
            return {"default_provider_id": default_provider_id, "providers": providers}
        except Exception as e:
            raise RuntimeError(f"PostgreSQL Load Insurance Config Error: {e}")
        finally:
            conn.close()

    def save_insurance_config(self, cfg: Dict[str, Any]) -> None:
        self._init_db()
        conn = self._connect()
        try:
            default_provider_id = cfg.get("default_provider_id")
            providers = cfg.get("providers", [])

            with conn.cursor() as cur:
                for prov in providers:
                    if isinstance(prov, dict):
                        pid = prov.get("provider_id")
                        if not pid:
                            continue
                        name = prov.get("name") or pid
                        abbrev = prov.get("abbreviation") or ""
                        purl = prov.get("policy_url") or ""
                        is_def = (pid == default_provider_id)

                        cur.execute(f"""
                            INSERT INTO {self.schema}.insurance_providers (provider_id, name, abbreviation, policy_url, is_default, updated_at)
                            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                            ON CONFLICT (provider_id) DO UPDATE SET
                                name = EXCLUDED.name,
                                abbreviation = EXCLUDED.abbreviation,
                                policy_url = EXCLUDED.policy_url,
                                is_default = EXCLUDED.is_default,
                                updated_at = CURRENT_TIMESTAMP;
                        """, (pid, name, abbrev, purl, is_def))

                        plans = prov.get("plans", [])
                        for plan in plans:
                            if isinstance(plan, dict):
                                plan_id = plan.get("plan_id")
                                if not plan_id:
                                    continue
                                plan_name = plan.get("plan_name") or plan_id
                                plan_type = plan.get("plan_type") or "Commercial"
                                plan_url = plan.get("policy_url") or ""
                                plan_def = bool(plan.get("is_default", False))

                                cur.execute(f"""
                                    INSERT INTO {self.schema}.insurance_plans (plan_id, provider_id, plan_name, plan_type, policy_url, is_default, updated_at)
                                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                                    ON CONFLICT (plan_id) DO UPDATE SET
                                        provider_id = EXCLUDED.provider_id,
                                        plan_name = EXCLUDED.plan_name,
                                        plan_type = EXCLUDED.plan_type,
                                        policy_url = EXCLUDED.policy_url,
                                        is_default = EXCLUDED.is_default,
                                        updated_at = CURRENT_TIMESTAMP;
                                """, (plan_id, pid, plan_name, plan_type, plan_url, plan_def))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"PostgreSQL Save Insurance Config Error: {e}")
        finally:
            conn.close()

    # ── CPT Code Map Methods ─────────────────────────────────────────
    def load_cpt_code_map(self) -> Dict[str, Any]:
        self._init_db()
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT cpt_code, procedure_name, department, test_case FROM {self.schema}.cpt_code_map;")
                rows = cur.fetchall()

            by_code = {}
            by_procedure = {}
            for code, proc, dept, tc in rows:
                by_code[code] = {
                    "procedure": proc,
                    "department": dept or "",
                    "test_case": tc or ""
                }
                if proc:
                    by_procedure[proc.lower().strip()] = code

            return {
                "by_code": by_code,
                "by_procedure": by_procedure,
                "updated_at": datetime.datetime.now().isoformat()
            }
        except Exception as e:
            raise RuntimeError(f"PostgreSQL Load CPT Code Map Error: {e}")
        finally:
            conn.close()

    def save_cpt_code_map(self, cpt_map: Dict[str, Any]) -> None:
        self._init_db()
        conn = self._connect()
        try:
            by_code = cpt_map.get("by_code", {})
            with conn.cursor() as cur:
                for code, info in by_code.items():
                    if not isinstance(info, dict):
                        continue
                    proc = info.get("procedure") or "Unknown"
                    dept = info.get("department") or ""
                    tc = info.get("test_case") or ""

                    cur.execute(f"""
                        INSERT INTO {self.schema}.cpt_code_map (cpt_code, procedure_name, department, test_case, updated_at)
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (cpt_code) DO UPDATE SET
                            procedure_name = EXCLUDED.procedure_name,
                            department = EXCLUDED.department,
                            test_case = EXCLUDED.test_case,
                            updated_at = CURRENT_TIMESTAMP;
                    """, (str(code), proc, dept, tc))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"PostgreSQL Save CPT Code Map Error: {e}")
        finally:
            conn.close()
