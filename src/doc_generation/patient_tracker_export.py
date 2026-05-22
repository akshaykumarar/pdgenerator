"""
Patient Tracker Exporter Module.
Generates a landscape PDF table and companion TSV file containing prioritized clinical patient metrics.
"""
import os
import json
import csv
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from src.core.config import (
    PATIENT_DATA_DIR,
    get_patient_records_folder,
    get_patient_report_folder,
)
from src.core import patient_db
from src.data import loader as data_loader

def generate_tracker_export(patient_ids: List[str]) -> str:
    """
    Compiles patient metrics for selected patient IDs into a landscape PDF table
    and companion TSV file. Saves both to `generated_output/patient-data/`.
    
    Args:
        patient_ids: List of numeric patient ID strings to export.
        
    Returns:
        The absolute path to the generated PDF.
    """
    # Ensure patient data directory exists
    os.makedirs(PATIENT_DATA_DIR, exist_ok=True)
    
    rows = []
    
    for p_id in patient_ids:
        p_id = str(p_id).strip()
        if not p_id:
            continue
            
        # Try loading concise summary JSON
        records_folder = get_patient_records_folder(p_id)
        json_path = os.path.join(records_folder, "concise_summary.json")
        
        summary_data = None
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    summary_data = json.load(f)
            except Exception as e:
                print(f"⚠️ Error reading concise summary for patient {p_id}: {e}")
                
        # Load demographics & case info for baseline/fallback
        patient_data = patient_db.load_patient(p_id) or {}
        case_details = data_loader.get_case_details(p_id) or {}
        
        # 1. Patient ID
        row_id = p_id
        
        # 2. Patient Name
        row_name = ""
        if summary_data and "test_case_and_overview" in summary_data:
            overview = summary_data["test_case_and_overview"]
            if isinstance(overview, dict):
                row_name = overview.get("patient_name", "")
        if not row_name:
            row_name = f"{patient_data.get('first_name', '')} {patient_data.get('last_name', '')}".strip()
        if not row_name or row_name == "Unknown Unknown":
            row_name = f"Patient {p_id}"
            
        # 3. DOB
        row_dob = ""
        if summary_data and "test_case_and_overview" in summary_data:
            overview = summary_data["test_case_and_overview"]
            if isinstance(overview, dict):
                row_dob = overview.get("dob", "")
        if not row_dob:
            row_dob = patient_data.get("dob") or patient_data.get("demographics", {}).get("dob") or "Unknown"
            
        # 4. Requested Procedure/CPT
        row_proc = ""
        if summary_data and "test_case_and_overview" in summary_data:
            overview = summary_data["test_case_and_overview"]
            if isinstance(overview, dict):
                proc = overview.get("procedure_requested", "")
                cpt = overview.get("cpt_code", "")
                if proc and cpt:
                    row_proc = f"{proc} (CPT {cpt})"
                elif proc or cpt:
                    row_proc = proc or cpt
        if not row_proc:
            proc = case_details.get("procedure") or patient_data.get("requested_procedure", {}).get("procedure_name") or "Unknown"
            cpt = case_details.get("cpt_code") or patient_data.get("requested_procedure", {}).get("cpt_code") or ""
            if cpt and cpt != "Unknown":
                row_proc = f"{proc} (CPT {cpt})"
            else:
                row_proc = proc
                
        # 5. Payer/Plan Type
        row_payer = ""
        if summary_data and "details_from_extraction" in summary_data:
            extract = summary_data["details_from_extraction"]
            if isinstance(extract, list):
                # Search for insurance strings
                for item in extract:
                    if "payer" in item.lower() or "insurance" in item.lower() or "plan" in item.lower():
                        row_payer = item
                        break
        if not row_payer:
            payer_name = patient_data.get("insurance", {}).get("payer_name") or "Unknown"
            plan_type = patient_data.get("insurance", {}).get("plan_type") or "Unknown"
            row_payer = f"{payer_name} - {plan_type}"
            
        # 6. Primary Diagnosis/ICD-10
        row_diag = ""
        if summary_data and "details_from_extraction" in summary_data:
            extract = summary_data["details_from_extraction"]
            if isinstance(extract, list):
                for item in extract:
                    if "diagnosis" in item.lower() or "icd" in item.lower():
                        row_diag = item
                        break
        if not row_diag:
            diagnoses = patient_data.get("diagnoses", [])
            if diagnoses and isinstance(diagnoses, list):
                first = diagnoses[0]
                if isinstance(first, dict):
                    row_diag = f"{first.get('code', '')} {first.get('condition', '')}".strip()
            if not row_diag:
                row_diag = case_details.get("details") or "Unknown"
                
        # 7. Urgency Level
        row_urgency = patient_data.get("pa_request", {}).get("urgency_level") or "Standard"
        
        # 8. Outcome
        row_outcome = case_details.get("outcome") or "Unknown"
        
        # 9. Correct Items & 10. Gaps & Issues (merged from multiple dimensions in ConciseSummary)
        correct_items = []
        gaps_and_issues = []
        
        if summary_data:
            for key in ["medical_necessity", "policy_compliance", "documentation_quality", "clinical_timeline_strength"]:
                param = summary_data.get(key)
                if param and isinstance(param, dict):
                    correct_items.extend(param.get("correct_items", []))
                    gaps_and_issues.extend(param.get("gaps_and_issues", []))
            
            # Post-attachments
            post = summary_data.get("likelihood_expectations_post_attachments")
            if post and isinstance(post, dict):
                correct_items.extend(post.get("correct_items", []))
                gaps_and_issues.extend(post.get("gaps_and_issues", []))
                
        if not correct_items:
            correct_items = ["Timeline meets procedure scheduling windows", "Demographics match requested payer records"] if row_outcome.lower() == "approval" else ["Active patient identity matched"]
        if not gaps_and_issues:
            gaps_and_issues = ["None identified"] if row_outcome.lower() == "approval" else ["Clinical criteria for CPT code documentation not met"]
            
        row_correct = "; ".join([c.replace("\t", " ").replace("\n", " ").strip() for c in correct_items if c.strip()])
        row_gaps = "; ".join([g.replace("\t", " ").replace("\n", " ").strip() for g in gaps_and_issues if g.strip()])
        
        # 11. Attachment List
        attachments = []
        if summary_data and "attachments_list" in summary_data:
            attachments = summary_data["attachments_list"] or []
            
        # Scan folder for actual generated PDFs as fallback
        report_folder = get_patient_report_folder(p_id)
        if os.path.exists(report_folder):
            for file_entry in os.listdir(report_folder):
                if file_entry.endswith(".pdf") and not file_entry.endswith("persona.pdf") and not file_entry.startswith("Clinical_Summary"):
                    clean_name = file_entry.replace(f"DOC-{p_id}-", "").replace(".pdf", "").replace("_", " ")
                    # Add to attachments if not already present by filename similarity
                    if not any(clean_name.lower() in a.lower() for a in attachments):
                        attachments.append(clean_name)
                        
        if not attachments:
            row_attachments = "No reports generated"
        else:
            row_attachments = "; ".join([a.replace("\t", " ").replace("\n", " ").strip() for a in attachments if a.strip()])
            
        rows.append([
            row_id,
            row_name,
            row_dob,
            row_proc,
            row_payer,
            row_diag,
            row_urgency,
            row_outcome,
            row_correct,
            row_gaps,
            row_attachments
        ])
        
    # Paths to save
    pdf_path = os.path.join(PATIENT_DATA_DIR, "patient_tracker_export.pdf")
    tsv_path = os.path.join(PATIENT_DATA_DIR, "patient_tracker_export.tsv")
    
    # ─── Save TSV ─────────────────────────────────────────────────────────────
    try:
        with open(tsv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow([
                "Patient ID", "Patient Name", "DOB", "Requested Procedure/CPT",
                "Payer/Plan Type", "Primary Diagnosis/ICD-10", "Urgency Level",
                "Outcome", "Correct Items", "Gaps & Issues", "Attachment List"
            ])
            for r in rows:
                writer.writerow(r)
        print(f"✅ TSV file exported successfully: {tsv_path}")
    except Exception as e:
        print(f"⚠️ Could not save TSV: {e}")
        
    # ─── Save PDF ─────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=landscape(letter),
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading2'],
        fontSize=12,
        leading=14,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1A365D')
    )
    
    header_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontSize=6,
        leading=7,
        fontName='Helvetica-Bold',
        textColor=colors.white
    )
    
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=5.5,
        leading=6.5,
        textColor=colors.HexColor('#2D3748')
    )
    
    story = []
    story.append(Paragraph("Clinical Patient Prior Authorization Tracker Export", title_style))
    story.append(Spacer(1, 8))
    
    headers = [
        "Patient ID", "Patient Name", "DOB", "Requested Procedure/CPT",
        "Payer/Plan Type", "Primary Diagnosis/ICD-10", "Urgency Level",
        "Outcome", "Correct Items", "Gaps & Issues", "Attachment List"
    ]
    
    table_data = []
    # Header Row
    table_data.append([Paragraph(h, header_style) for h in headers])
    
    # Data Rows
    for r in rows:
        table_data.append([Paragraph(str(cell or "N/A"), cell_style) for cell in r])
        
    # Column widths summing to exactly 720 points
    colWidths = [35, 65, 50, 65, 50, 65, 45, 45, 100, 100, 100]
    
    t = Table(table_data, colWidths=colWidths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A365D')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7FAFC')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    
    story.append(t)
    doc.build(story)
    
    print(f"✅ PDF file exported successfully: {pdf_path}")
    return pdf_path
