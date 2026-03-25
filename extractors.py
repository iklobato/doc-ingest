import re
import pdfplumber
from pathlib import Path
from typing import Optional


LABEL_PATTERN = re.compile(
    r"^\s*(?:bill\s*to|ship\s*to|ship\s*mode|date|invoice|balance\s*due|item|quantity|rate|amount|subtotal|discount|shipping|total|notes|terms|order\s*id|#)\s*:",
    re.IGNORECASE,
)


def extract_client_name(pdf_path: Path) -> Optional[str]:
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    if not text.strip():
        return None

    lines = text.strip().split("\n")

    for i, line in enumerate(lines):
        if not re.search(r"bill\s*to\s*:", line, re.IGNORECASE):
            continue

        candidate_lines = []
        for j in range(i + 1, min(i + 4, len(lines))):
            next_line = lines[j].strip()
            if not next_line or LABEL_PATTERN.match(next_line):
                continue
            candidate_lines.append(next_line)

        if not candidate_lines:
            continue

        return " ".join(candidate_lines[:2])

    return None


def get_invoice_files(files_dir: Path, pattern: str) -> list[Path]:
    return sorted(files_dir.glob(pattern))


NOTES_LABEL_PATTERN = re.compile(
    r"^\s*notes?\s*:",
    re.IGNORECASE,
)


def extract_notes(pdf_path: Path) -> Optional[str]:
    """
    Extract notes text from invoice PDF.

    Looks for 'Notes:' or 'Note:' label and captures all text until
    the next label (Terms, Order ID, etc.) or end of document.

    Returns the notes text or None if not found.
    """
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    if not text.strip():
        return None

    lines = text.strip().split("\n")

    for i, line in enumerate(lines):
        if not NOTES_LABEL_PATTERN.match(line.strip()):
            continue

        candidate_lines = []
        for j in range(i + 1, min(i + 10, len(lines))):
            next_line = lines[j].strip()
            if not next_line:
                continue
            if LABEL_PATTERN.match(next_line):
                break
            candidate_lines.append(next_line)

        if not candidate_lines:
            continue

        return "\n".join(candidate_lines).strip()

    return None


def extract_field(text: str, field_name: str) -> Optional[str]:
    """
    Extract a field value from invoice text by field name.

    Args:
        text: Full invoice text
        field_name: Field label to search for (e.g., 'date', 'invoice', 'total')

    Returns:
        The field value or None if not found.
    """
    pattern = re.compile(
        rf"^\s*{re.escape(field_name)}\s*:\s*(.+)$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def extract_all_fields(pdf_path: Path) -> dict:
    """
    Extract all relevant fields from an invoice PDF.

    Returns a dict with:
        - client_name: From 'Bill To' field
        - invoice_number: From 'Order ID' field
        - date: From 'Date' field
        - amount: From 'Total' field
        - notes: From 'Notes' field
    """
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    return {
        "client_name": extract_client_name(pdf_path),
        "invoice_number": extract_field(text, "Order ID"),
        "date": extract_field(text, "Date"),
        "amount": extract_field(text, "Total"),
        "notes": extract_notes(pdf_path),
    }
