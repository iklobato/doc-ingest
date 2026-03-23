#!/usr/bin/env python3
"""
Doc Ingest - Document Ingestion to Legal Matter Management

Extracts client names from PDF invoices and:
1. Creates matters in Eve for each unique client
2. Uploads each invoice to the appropriate matter
"""

import sys
from pathlib import Path

from config import FILES_DIR, INVOICE_PATTERN
from models import Client
from services import EveMatterService
from extractors import get_invoice_files, extract_client_name


def group_files_by_client(files: list[Path]) -> dict[str, list[Path]]:
    client_groups = {}
    for pdf_file in files:
        client_name = extract_client_name(pdf_file)
        if not client_name:
            print(f"  WARNING: Could not extract client from {pdf_file.name}")
            continue
        if client_name not in client_groups:
            client_groups[client_name] = []
        client_groups[client_name].append(pdf_file)
        print(f"  {pdf_file.name} -> {client_name}")
    return client_groups


def main():
    print("=" * 60)
    print("Doc Ingest - Document Ingestion")
    print("=" * 60)

    files_dir = Path(FILES_DIR)
    if not files_dir.exists():
        print(f"\nERROR: Files directory does not exist: {files_dir}")
        print("Please add the invoice PDFs to this directory first.")
        sys.exit(1)

    print(f"\n[1] Scanning for invoice files in {files_dir}")
    print(f"    Pattern: {INVOICE_PATTERN}")

    invoice_files = get_invoice_files(files_dir, INVOICE_PATTERN)

    if not invoice_files:
        print(f"\nERROR: No files found matching {INVOICE_PATTERN}")
        sys.exit(1)

    print(f"\n    Found {len(invoice_files)} invoice file(s):")

    print(f"\n[2] Extracting client names from invoices")
    client_groups = group_files_by_client(invoice_files)

    if not client_groups:
        print("\nERROR: Could not extract any client names from invoices")
        sys.exit(1)

    print(f"\n    Found {len(client_groups)} unique client(s):")
    for client, files in client_groups.items():
        print(f"      - {client}: {len(files)} file(s)")

    print(f"\n[3] Creating/verifying matters in Eve")
    service = EveMatterService()

    matter_map = {}
    for client_name, files in client_groups.items():
        client = Client(name=client_name, files=files)
        matter_id = service.create_or_update_matter(client)
        matter_map[client_name] = matter_id
        print(f"    Creating matter: {client_name} (id: {matter_id})")
        print(f"      Matter created/updated")

    print(f"\n[4] Uploading documents to matters")
    total_uploaded = 0
    total_skipped = 0
    total_failed = 0

    for client_name, files in client_groups.items():
        matter_id = matter_map[client_name]
        print(f"\n    Client: {client_name}")

        for file_path in files:
            print(f"      Uploading: {file_path.name}")
            try:
                result = service.upload_invoice(matter_id, file_path)
                if result.status == "uploaded":
                    print(f"        Uploaded successfully")
                    total_uploaded += 1
                elif result.status == "skipped":
                    print(f"        Skipped (already exists)")
                    total_skipped += 1
            except Exception as e:
                print(f"        Failed: {e}")
                total_failed += 1

    print(f"\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Clients processed: {len(client_groups)}")
    print(f"  Documents processed: {total_uploaded + total_skipped}")
    print(f"  Documents skipped (already exist): {total_skipped}")
    print(f"  Documents failed: {total_failed}")
    print("=" * 60)


if __name__ == "__main__":
    main()
