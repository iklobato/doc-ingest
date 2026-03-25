#!/usr/bin/env python3
"""
Doc Ingest - Document Ingestion to Legal Matter Management

Extracts client names from PDF invoices and:
1. Creates matters in Eve for each unique client
2. Uploads each invoice to the appropriate matter
"""

import sys
import logging
from pathlib import Path

from config import FILES_DIR, INVOICE_PATTERN
from models import Client
from services import EveMatterService
from extractors import get_invoice_files, extract_client_name

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def group_files_by_client(files: list[Path]) -> dict[str, list[Path]]:
    client_groups = {}
    for pdf_file in files:
        client_name = extract_client_name(pdf_file)
        if not client_name:
            logger.warning(f"Could not extract client from {pdf_file.name}")
            continue
        if client_name not in client_groups:
            client_groups[client_name] = []
        client_groups[client_name].append(pdf_file)
    return client_groups


def main():
    files_dir = Path(FILES_DIR)
    if not files_dir.exists():
        logger.error(f"Files directory does not exist: {files_dir}")
        sys.exit(1)

    invoice_files = get_invoice_files(files_dir, INVOICE_PATTERN)

    if not invoice_files:
        logger.error(f"No files found matching {INVOICE_PATTERN}")
        sys.exit(1)

    logger.info(f"Found {len(invoice_files)} invoice file(s)")

    client_groups = group_files_by_client(invoice_files)

    if not client_groups:
        logger.error("Could not extract any client names from invoices")
        sys.exit(1)

    logger.info(f"Found {len(client_groups)} unique client(s)")

    service = EveMatterService()

    matter_map = {}
    for client_name, files in client_groups.items():
        client = Client(name=client_name, files=files)
        matter_id = service.create_or_update_matter(client)
        matter_map[client_name] = matter_id

    total_uploaded = 0
    total_skipped = 0
    total_failed = 0

    for client_name, files in client_groups.items():
        matter_id = matter_map[client_name]

        for file_path in files:
            try:
                result = service.upload_invoice(matter_id, file_path)
                if result.status == "uploaded":
                    total_uploaded += 1
                elif result.status == "skipped":
                    total_skipped += 1
            except Exception as e:
                logger.error(f"Failed to upload {file_path.name}: {e}")
                total_failed += 1

    logger.info(
        f"Processed: {total_uploaded + total_skipped}, Skipped: {total_skipped}, Failed: {total_failed}"
    )

    print("\n" + "=" * 70)
    print("MATTERS SUMMARY")
    print("=" * 70)

    all_matters = service.list_matters()

    for matter in all_matters:
        matter_id = matter.get("externalId")
        if not matter_id:
            continue

        status = "CLOSED" if matter.get("closed") else "OPEN"
        print(f"\n[{status}] {matter.get('name')}")
        print(f"  External ID: {matter_id}")
        print(f"  Visibility: {matter.get('visibility')}")
        print(f"  Created: {matter.get('createdAt')}")
        print(f"  Updated: {matter.get('updatedAt')}")

        users = matter.get("associatedUsers", [])
        if users:
            print(f"  Users: {', '.join(u.get('email', 'N/A') for u in users)}")

        notes = service.get_matter_notes(matter_id)
        if notes:
            print(f"  Notes ({len(notes)}):")
            for note in notes:
                title = note.get("title") or "Untitled"
                author = note.get("authorEmail") or "Unknown"
                body_preview = note.get("body", "")[:100]
                if len(note.get("body", "")) > 100:
                    body_preview += "..."
                print(f"    - [{title}] by {author}")
                print(f"      {body_preview}")
        else:
            print(f"  Notes: None")

        docs = service.get_matter_documents(matter_id)
        if docs:
            print(f"  Documents ({len(docs)}):")
            for doc in docs:
                print(f"    - {doc.get('fileName')} ({doc.get('status')})")
        else:
            print(f"  Documents: None")

    print("\n" + "=" * 70)
    print(f"Total: {len(all_matters)} matters")


if __name__ == "__main__":
    main()
