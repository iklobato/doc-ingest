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



def extract_notes(pdf_path: Path) -> Optional[str]:
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

