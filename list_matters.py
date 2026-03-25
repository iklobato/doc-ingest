#!/usr/bin/env python3
"""
List Matters - Fetch all matters from Eve API with full details.

Usage:
    python list_matters.py
    python list_matters.py --output matters.json
    python list_matters.py --verbose
"""

import argparse
import json
import logging
from typing import Any

import requests

from config import BASE_URL, API_KEY

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class EveAPIClient:
    def __init__(self, base_url: str = BASE_URL, api_key: str = API_KEY):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    def list_matters(self, limit: int = 100) -> list[dict]:
        """Fetch all matters with pagination."""
        all_matters = []
        cursor = None

        while True:
            params = {"limit": limit}
            if cursor:
                params["cursor"] = cursor

            response = self._request("GET", "/v1/matters", params=params)
            data = response.json()

            all_matters.extend(data.get("items", []))

            if not data.get("hasNext"):
                break
            cursor = data.get("nextCursor")

        return all_matters

    def get_matter(self, matter_id: str) -> dict:
        """Get full matter details by external ID."""
        response = self._request("GET", f"/v1/matters/{matter_id}")
        return response.json()


def format_matter(matter: dict, verbose: bool = False) -> dict:
    """Format matter data for display."""
    result = {
        "id": matter.get("id"),
        "external_id": matter.get("externalId"),
        "name": matter.get("name"),
        "closed": matter.get("closed"),
        "visibility": matter.get("visibility"),
        "created_at": matter.get("createdAt"),
        "updated_at": matter.get("updatedAt"),
    }

    if verbose:
        result["associated_users"] = [
            {"email": u.get("email"), "name": u.get("name")}
            for u in matter.get("associatedUsers", [])
        ]

    return result


def list_matters(output: str | None = None, verbose: bool = False) -> list[dict]:
    """Fetch and optionally save all matters."""
    client = EveAPIClient()

    logger.info("Fetching matters...")
    matters = client.list_matters()
    logger.info(f"Found {len(matters)} matter(s)")

    formatted = [format_matter(m, verbose) for m in matters]

    if output:
        with open(output, "w") as f:
            json.dump(formatted, f, indent=2)
        logger.info(f"Saved to {output}")

    return formatted


def main():
    parser = argparse.ArgumentParser(description="List all matters from Eve API")
    parser.add_argument("--output", "-o", type=str, help="Output JSON file path")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Include associated users"
    )
    args = parser.parse_args()

    matters = list_matters(output=args.output, verbose=args.verbose)

    print(f"\n{'=' * 60}")
    print(f"MATTERS SUMMARY ({len(matters)} total)")
    print(f"{'=' * 60}\n")

    for m in matters:
        status = "CLOSED" if m["closed"] else "OPEN"
        print(f"[{status}] {m['name']}")
        print(f"  External ID: {m['external_id']}")
        print(f"  Created: {m['created_at']}")
        print(f"  Updated: {m['updated_at']}")
        if "associated_users" in m and m["associated_users"]:
            for u in m["associated_users"]:
                print(f"  User: {u['email']} ({u['name'] or 'N/A'})")
        print()


if __name__ == "__main__":
    main()
