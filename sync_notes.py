#!/usr/bin/env python3
"""
Sync Notes - Extract notes from PDF invoices and sync to Eve matters.

This script runs after main.py ingestion to:
1. Scan PDF files for extracted notes
2. Match each PDF to its corresponding matter
3. Sync notes to the matter via Eve API

Usage:
    python sync_notes.py
    python sync_notes.py --dry-run
"""

import argparse
import json
import logging
import re
import requests
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber

from config import FILES_DIR, INVOICE_PATTERN, BASE_URL, API_KEY, USER_EMAIL
from utils import slugify
from extractors import extract_client_name

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def extract_notes_from_pdf(pdf_path: Path) -> str | None:
    """Extract notes text from invoice PDF."""
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    if not text.strip():
        return None

    match = re.search(
        r"(?:^|\n)\s*notes?\s*:\s*\n?(.*?)(?=\n\s*(?:terms|order\s*id|#)|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    return None


def get_pdfs_with_notes(files_dir: Path, pattern: str) -> list[tuple[Path, str]]:
    """Scan PDFs and extract notes. Returns list of (pdf_path, notes_text)."""
    results = []
    for pdf_path in sorted(files_dir.glob(pattern)):
        notes = extract_notes_from_pdf(pdf_path)
        if notes:
            results.append((pdf_path, notes))
            logger.info(f"Found notes in: {pdf_path.name}")
        else:
            logger.debug(f"No notes in: {pdf_path.name}")
    return results


class EveAPIClient:
    """Lightweight Eve API client for note sync."""

    def __init__(self, base_url: str = BASE_URL, api_key: str = API_KEY):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        import requests

        url = f"{self.base_url}{path}"
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    def get_matter_id_from_slug(self, slug: str) -> str | None:
        """Get internal matter ID from external slug."""
        try:
            response = self._request("GET", f"/v1/matters/{slug}")
            data = response.json()
            return data.get("matter", {}).get("id") or slug
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def sync_note(
        self,
        matter_external_id: str,
        external_id: str,
        body: str,
        title: str,
    ) -> dict:
        """Sync a single note to a matter."""
        payload = {
            "externalMatterId": matter_external_id,
            "syncNotes": [
                {
                    "externalId": external_id,
                    "body": body,
                    "title": title,
                    "authorEmail": USER_EMAIL,
                    "authorName": USER_EMAIL.split("@")[0] if USER_EMAIL else "System",
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
        response = self._request("POST", "/v1/notes/batch-sync", json=payload)
        return response.json()


def sync_notes_to_matters(dry_run: bool = False) -> dict:
    """Main sync logic. Returns statistics."""
    files_dir = Path(FILES_DIR)
    if not files_dir.exists():
        logger.error(f"Files directory does not exist: {files_dir}")
        return {"synced": 0, "skipped": 0, "failed": 0}

    pdfs_with_notes = get_pdfs_with_notes(files_dir, INVOICE_PATTERN)

    if not pdfs_with_notes:
        logger.info("No notes found in any PDF files")
        return {"synced": 0, "skipped": 0, "failed": 0}

    logger.info(f"Found {len(pdfs_with_notes)} file(s) with notes")

    stats = {"synced": 0, "skipped": 0, "failed": 0}
    client = EveAPIClient() if not dry_run else None

    for pdf_path, notes_body in pdfs_with_notes:
        # Extract client name from PDF to get correct matter slug
        client_name = extract_client_name(pdf_path)
        if not client_name:
            logger.warning(
                f"Could not extract client name from {pdf_path.name}, skipping note sync"
            )
            stats["skipped"] += 1
            continue

        matter_slug = slugify(client_name)

        if dry_run:
            logger.info(f"[DRY-RUN] Would sync note for: {pdf_path.name}")
            logger.info(f"  Matter slug: {matter_slug}")
            logger.info(f"  Note title: Invoice Notes - {pdf_path.name}")
            stats["skipped"] += 1
            continue

        try:
            note_external_id = f"note-{pdf_path.stem}"
            title = f"Invoice Notes - {pdf_path.name}"

            assert client is not None  # For type checker
            result = client.sync_note(
                matter_external_id=matter_slug,
                external_id=note_external_id,
                body=notes_body,
                title=title,
            )

            logger.info(f"Synced note for: {pdf_path.name}")
            stats["synced"] += 1

        except requests.HTTPError as e:
            logger.error(f"Failed to sync note for {pdf_path.name}: {e}")
            if e.response is not None:
                logger.error(f"  Response: {e.response.text}")
            stats["failed"] += 1
        except Exception as e:
            logger.error(f"Failed to sync note for {pdf_path.name}: {e}")
            stats["failed"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Sync notes from PDFs to Eve matters")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without making changes"
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("=== DRY-RUN MODE - No changes will be made ===")

    stats = sync_notes_to_matters(dry_run=args.dry_run)

    logger.info(
        f"Notes sync complete: Synced={stats['synced']}, "
        f"Skipped={stats['skipped']}, Failed={stats['failed']}"
    )


if __name__ == "__main__":
    main()
