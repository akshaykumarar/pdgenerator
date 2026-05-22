import os
import json
import re
from typing import List, Dict
from ..core.config import DEBUG_DIR, MAX_SUPPORTING_DOCUMENTS

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES_PATH = os.path.join(_BASE_DIR, "templates", "document_plan_rules.json")

def ensure_debug_dir():
    try:
        if not os.path.exists(DEBUG_DIR):
            try:
                os.makedirs(DEBUG_DIR, exist_ok=True)
            except Exception as e:
                # Ignore errors here to prevent blocking main flow
                pass
        elif not os.path.isdir(DEBUG_DIR):
            print(f"⚠️ Warning: {DEBUG_DIR} is not a directory.")
    except Exception as e:
        print(f"⚠️ Could not ensure debug dir: {e}")

def load_rules() -> Dict:
    """Loads document plan rules from the templates directory."""
    if os.path.exists(RULES_PATH):
        try:
            with open(RULES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading {RULES_PATH}: {e}")
    return {}

def detect_case_type(procedure_string: str, cpt_code: str = "") -> str:
    """
    Detects the case type string based on the provided CPT code or procedure string.
    Rules:
    HCPCS J/Q codes (e.g. J0897, Q5124) → 'medication'
    70000–79999 → 'imaging'
    10000–69999 → 'surgery'
    97000–97999 → 'therapy'
    medication keywords -> 'medication'
    default → 'diagnostic'
    """
    if not procedure_string:
        return "diagnostic"
        
    rules = load_rules()
    
    # Extract CPT from explicit param or procedure string
    cpt_code = str(cpt_code or "").strip()
    if not cpt_code:
        # First check for HCPCS drug codes (J or Q followed by 4 digits)
        hcpcs_match = re.search(r"\b([JQjq]\d{4})\b", str(procedure_string))
        if hcpcs_match:
            cpt_code = hcpcs_match.group(1)
        else:
            cpt_match = re.search(r"(\d{5})", str(procedure_string))
            if cpt_match:
                cpt_code = cpt_match.group(1)

    if cpt_code:
        # Check for HCPCS drug codes
        if re.search(r"^[JQjq]\d{4}$", cpt_code):
            return "medication"
            
        # Attempt integer parsing for ranges
        try:
            cpt_int = int(cpt_code)
            if 10000 <= cpt_int <= 69999:
                return "surgery"
            elif 70000 <= cpt_int <= 79999:
                return "imaging"
            elif 97000 <= cpt_int <= 97999:
                return "therapy"
        except Exception:
            pass
            
    # Fallback to keyword matching for medications
    proc_lower = str(procedure_string).lower()
    med_keywords = rules.get("medication", {}).get("keywords", ["infusion", "injection", "prescription", "medication", "drug"])
    for kw in med_keywords:
        if kw in proc_lower:
            return "medication"
            
    # Default
    return "diagnostic"

def select_document_plan(case_type: str) -> List[str]:
    """
    Loads templates/document_plan_rules.json and returns a list of template filenames
    for the specified case_type, capping supporting documents to MAX_SUPPORTING_DOCUMENTS = 5.
    """
    rules = load_rules()
    templates = []
    if case_type in rules:
        templates = rules[case_type].get("templates", [])
    else:
        # Fallback default plan
        templates = ["prior_auth_request_template.json", "summary_template.json"]
        
    # Separate supporting from core templates
    core_before = []
    supporting = []
    core_after = []
    
    for t in templates:
        is_core = t == "prior_auth_request_template.json" or "summary" in t
        if is_core:
            # Usually prior_auth is first, summary is last.
            if t == "prior_auth_request_template.json":
                core_before.append(t)
            else:
                core_after.append(t)
        else:
            supporting.append(t)
            
    # Cap supporting templates
    capped_supporting = supporting[:MAX_SUPPORTING_DOCUMENTS]
    
    return core_before + capped_supporting + core_after

def create_and_save_document_plan(patient_id: str, case_data: Dict) -> Dict:

    """
    Orchestration wrapper that detects case type, loads the plan templates,
    and writes out the debug plan representation.
    """
    procedure = case_data.get("procedure", "")
    case_type = detect_case_type(procedure, cpt_code=case_data.get("cpt_code", ""))
    templates = select_document_plan(case_type)
    
    plan = {
        "case_type": case_type,
        "procedure": procedure,
        "document_templates": templates
    }
    
    ensure_debug_dir()
    path = os.path.join(DEBUG_DIR, "document_plan.json")
    with open(path, "w", encoding='utf-8') as f:
        json.dump(plan, f, indent=2)
        
    return plan
