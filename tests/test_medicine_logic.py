import pytest
from src.ai.models import MedicationEntry, PARequestDetails
from src.doc_generation.planner import detect_case_type, select_document_plan
from src.data.patient_record_writer import write_patient_record

def test_medication_models():
    """Verify MedicationEntry and PARequestDetails support medicine-specific fields."""
    med = MedicationEntry(
        brand="Prolia",
        generic_name="Denosumab 60mg/mL",
        dosage="60mg SC Q6M",
        qty="1 prefilled syringe",
        prescribed_by="Dr. Sarah Jenkins, MD",
        status="current",
        start_date="01-15-2026",
        end_date="ongoing",
        reason="Osteoporosis",
        ndc_code="55513-0710-01",
        hcpcs_code="J0897",
        route="Subcutaneous",
        frequency="Every 6 months",
        days_supply="180 days",
        refills="1"
    )
    assert med.ndc_code == "55513-0710-01"
    assert med.hcpcs_code == "J0897"
    assert med.route == "Subcutaneous"

    pa = PARequestDetails(
        requesting_provider="Dr. Sarah Jenkins, MD",
        urgency_level="Routine",
        clinical_justification="Severe osteoporosis with prior fragility fracture.",
        supporting_diagnoses=["M81.0 - Age-related osteoporosis without current pathological fracture"],
        expected_outcome="Prevention of future bone fractures",
        ndc_code="55513-0710-01",
        hcpcs_code="J0897",
        administration_route="Subcutaneous",
        dosing_frequency="Every 6 months",
        days_supply="180 days",
        step_therapy_failed_agents=["Failed oral Alendronate due to severe esophageal ulceration"]
    )
    assert pa.ndc_code == "55513-0710-01"
    assert len(pa.step_therapy_failed_agents) == 1

def test_planner_medicine_case_detection_and_templates():
    """Verify planner detects medication case types and conditionally appends infusion_order_template."""
    case_type_j = detect_case_type("Denosumab Injection", cpt_code="J0897")
    assert case_type_j == "medication"

    case_type_q = detect_case_type("Rituximab Infusion", cpt_code="Q5124")
    assert case_type_q == "medication"

    # Oral medication without infusion keyword -> standard templates
    plan_oral = select_document_plan("medication", procedure_string="Oral Prescription Refill")
    assert "infusion_order_template.json" not in plan_oral
    assert "prior_auth_request_template.json" in plan_oral
    assert "lab_report_template.json" in plan_oral

    # Infusion drug -> conditionally attaches infusion_order_template.json
    plan_infusion = select_document_plan("medication", procedure_string="Denosumab Subcutaneous Infusion")
    assert "infusion_order_template.json" in plan_infusion

def test_patient_record_writer_medicine_output(tmp_path, monkeypatch):
    """Verify write_patient_record outputs NDC code, HCPCS code, and step therapy failed agents."""
    monkeypatch.setattr("src.data.patient_record_writer.get_patient_records_folder", lambda pid: str(tmp_path))
    
    persona = {
        "first_name": "Jane",
        "last_name": "Doe",
        "gender": "female",
        "dob": "05-12-1975",
        "race": "Caucasian",
        "height": "5 ft 6 in",
        "weight": "140 lbs",
        "pa_request": {
            "requesting_provider": "Dr. Smith",
            "urgency_level": "Routine",
            "clinical_justification": "Medical necessity",
            "ndc_code": "00006-0272-01",
            "hcpcs_code": "J0897",
            "administration_route": "Subcutaneous",
            "dosing_frequency": "Every 6 months",
            "days_supply": "180 days",
            "step_therapy_failed_agents": ["Oral bisphosphonates failed due to GERD"]
        },
        "medications": [
            {
                "brand": "Prolia",
                "generic_name": "Denosumab",
                "dosage": "60mg",
                "qty": "1 prefilled syringe",
                "prescribed_by": "Dr. Smith",
                "status": "current",
                "start_date": "01-01-2026",
                "end_date": "ongoing",
                "reason": "Osteoporosis",
                "ndc_code": "00006-0272-01",
                "hcpcs_code": "J0897",
                "route": "Subcutaneous",
                "frequency": "Q6M",
                "days_supply": "180 days"
            }
        ]
    }

    out_file = write_patient_record("999", persona, version=1, docs_generated=["DOC-999-001.pdf"])
    with open(out_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert "NDC Code (11-digit): 00006-0272-01" in content
    assert "HCPCS Drug Code: J0897" in content
    assert "Administration Route: Subcutaneous" in content
    assert "Oral bisphosphonates failed due to GERD" in content
    assert "NDC: 00006-0272-01" in content
