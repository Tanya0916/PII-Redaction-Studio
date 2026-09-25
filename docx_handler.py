import logging
from typing import Dict, List, Any
import docx
from docx.document import Document
from docx.text.paragraph import Paragraph
from docx.table import Table, _Cell

from pii_detector import PIIDetector
from anonymizer import PIIAnonymizer

logger = logging.getLogger("PIIRedactor")


class DOCXRedactor:
    """
    Handles reading DOCX files, detecting PII, anonymizing with consistent fake data,
    and writing out the redacted DOCX file while strictly preserving paragraph styles,
    run-level formatting (bold/italics/fonts), tables, headers, and footers.
    """

    def __init__(self, detector: PIIDetector, anonymizer: PIIAnonymizer):
        self.detector = detector
        self.anonymizer = anonymizer
        self.total_redactions = 0

    def _redact_paragraph(self, paragraph: Paragraph) -> int:
        """
        Detects and replaces PII within a single paragraph while preserving
        run-level formatting (bold, italic, font style, size, color).
        """
        text = paragraph.text
        if not text or not text.strip():
            return 0

        matches = self.detector.detect(text)
        if not matches:
            return 0

        redaction_count = len(matches)

        # To preserve formatting, we replace text run by run or using match mappings.
        # Simple & effective run-level replacement strategy:
        # Sort matches in reverse start index order
        sorted_matches = sorted(matches, key=lambda x: x["start"], reverse=True)

        for match in sorted_matches:
            target = match["text"]
            replacement = self.anonymizer.get_replacement(target, match["entity_type"])
            self._replace_text_in_paragraph_runs(paragraph, target, replacement)

        return redaction_count

    def _replace_text_in_paragraph_runs(self, paragraph: Paragraph, target: str, replacement: str) -> None:
        """
        Replaces target string with replacement across paragraph runs without destroying run formatting.
        """
        if target not in paragraph.text:
            return

        # Case 1: Target text is fully contained inside a single run
        for run in paragraph.runs:
            if target in run.text:
                run.text = run.text.replace(target, replacement)
                return

        # Case 2: Target text spans across multiple adjacent runs
        # Reconstruct full paragraph text position map to runs
        run_spans = []
        curr_pos = 0
        for run in paragraph.runs:
            run_len = len(run.text)
            run_spans.append((curr_pos, curr_pos + run_len, run))
            curr_pos += run_len

        full_text = paragraph.text
        start_idx = full_text.find(target)

        while start_idx != -1:
            end_idx = start_idx + len(target)

            # Find affected runs
            affected_runs = []
            for r_start, r_end, run in run_spans:
                if max(start_idx, r_start) < min(end_idx, r_end):
                    affected_runs.append((r_start, r_end, run))

            if affected_runs:
                # Put replacement in the first affected run, clear target text from remaining
                first_r_start, first_r_end, first_run = affected_runs[0]
                
                # Split prefix of first run if needed
                prefix_offset = start_idx - first_r_start
                prefix = first_run.text[:prefix_offset] if prefix_offset > 0 else ""
                
                last_r_start, last_r_end, last_run = affected_runs[-1]
                suffix_offset = end_idx - last_r_start
                suffix = last_run.text[suffix_offset:] if suffix_offset < len(last_run.text) else ""

                # Update first run text
                first_run.text = prefix + replacement

                # Clear intermediate runs
                for _, _, run in affected_runs[1:-1]:
                    run.text = ""

                if len(affected_runs) > 1:
                    last_run.text = suffix

            # Look for subsequent occurrences
            full_text = paragraph.text
            start_idx = full_text.find(target, start_idx + len(replacement))

    def _process_table(self, table: Table) -> int:
        """Recursively processes and redact all cells within a table."""
        count = 0
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    count += self._redact_paragraph(paragraph)
                # Recursively process nested tables if any
                for nested_table in cell.tables:
                    count += self._process_table(nested_table)
        return count

    def redact_document(self, input_path: str, output_path: str) -> Dict[str, Any]:
        """
        Loads input DOCX, processes paragraphs, tables, headers, footers,
        saves the redacted document to output_path, and returns summary stats.
        """
        logger.info(f"Opening DOCX document: {input_path}")
        doc = docx.Document(input_path)

        total_redactions = 0

        # 1. Process main document body paragraphs
        logger.info("Redacting main document body paragraphs...")
        for p in doc.paragraphs:
            total_redactions += self._redact_paragraph(p)

        # 2. Process document tables
        logger.info(f"Redacting {len(doc.tables)} document tables...")
        for t in doc.tables:
            total_redactions += self._process_table(t)

        # 3. Process headers and footers across all sections
        logger.info("Redacting headers and footers...")
        for section in doc.sections:
            if section.header:
                for hp in section.header.paragraphs:
                    total_redactions += self._redact_paragraph(hp)
                for ht in section.header.tables:
                    total_redactions += self._process_table(ht)

            if section.footer:
                for fp in section.footer.paragraphs:
                    total_redactions += self._redact_paragraph(fp)
                for ft in section.footer.tables:
                    total_redactions += self._process_table(ft)

        # Save redacted file
        logger.info(f"Saving redacted document to: {output_path}")
        doc.save(output_path)

        self.total_redactions = total_redactions
        summary = {
            "total_redactions": total_redactions,
            "unique_pii_detected": len(self.anonymizer.get_mapping_dict()),
            "output_path": output_path
        }
        logger.info(f"Redaction complete. Total redactions: {total_redactions}, Unique PII: {len(self.anonymizer.get_mapping_dict())}")
        return summary
