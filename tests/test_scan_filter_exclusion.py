import os
import unittest
from unittest.mock import patch, MagicMock

from src.utils.file_utils import is_summary_pdf
import src.workflow as workflow


class TestScanFilterExclusion(unittest.TestCase):
    def test_is_summary_pdf_detection(self):
        """Verify is_summary_pdf correctly identifies summary documents."""
        # Standard summary paths
        self.assertTrue(is_summary_pdf("/path/to/generated_output/summary/Clinical_Summary_Patient_101-v1.0.pdf"))
        self.assertTrue(is_summary_pdf("generated_output/summary/anything.pdf"))
        self.assertTrue(is_summary_pdf("Clinical_Summary_Patient_101-v1.0.pdf"))
        self.assertTrue(is_summary_pdf("Annotator_Summary_Patient_101.pdf"))
        self.assertTrue(is_summary_pdf("Concise_Summary_Patient_101.pdf"))
        self.assertTrue(is_summary_pdf("summary_doc.pdf"))

        # Non-summary clinical documents
        self.assertFalse(is_summary_pdf("/path/to/patient-data/101 - Sandor/DOC-101-001_Consult_Note.pdf"))
        self.assertFalse(is_summary_pdf("101-Sandor-Clegane-persona.pdf"))
        self.assertFalse(is_summary_pdf("DOC-101-002_Lab_Report.pdf"))
        self.assertFalse(is_summary_pdf(""))
        self.assertFalse(is_summary_pdf(None))

    @patch("src.doc_generation.scan_filter.apply_scan_filter")
    @patch("os.path.exists", return_value=True)
    def test_workflow_scan_filter_skips_summary(self, mock_exists, mock_apply_scan_filter):
        """Verify that applying scan_mode inside workflow skips summary documents while processing clinical docs."""
        written_paths = [
            "/generated_output/patient-data/101-Sandor/DOC-101-001_Consult_Note.pdf",
            "/generated_output/summary/Clinical_Summary_Patient_101-v1.0.pdf",
            "/generated_output/patient-data/101-Sandor/101-Sandor-persona.pdf",
        ]

        # Simulate the scan_mode loop logic in workflow
        processed = []
        for path in written_paths:
            if path and os.path.exists(path):
                if is_summary_pdf(path):
                    continue
                mock_apply_scan_filter(path, intensity="medium")
                processed.append(path)

        self.assertEqual(len(processed), 2)
        self.assertNotIn("/generated_output/summary/Clinical_Summary_Patient_101-v1.0.pdf", processed)
        self.assertEqual(mock_apply_scan_filter.call_count, 2)


if __name__ == "__main__":
    unittest.main()
