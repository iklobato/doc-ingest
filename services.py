import requests
from pathlib import Path
from typing import Protocol
import logging
from typing import Optional

from models import Client, UploadResult
from config import BASE_URL, API_KEY, USER_EMAIL
from utils import slugify


class MatterService(Protocol):
    def create_or_update_matter(self, client: Client) -> str: ...
    def upload_invoice(self, matter_id: str, file_path: Path) -> UploadResult: ...


class EveMatterService:
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

    def create_or_update_matter(self, client: Client) -> str:
        external_id = slugify(client.name)
        payload = {
            "name": client.name,
            "associatedUsers": [{"email": USER_EMAIL}],
            "closed": False,
            "visibility": "ORG",
        }
        response = self._request("PUT", f"/v1/matters/{external_id}", json=payload)
        response.raise_for_status()
        matter_external_id = response.json().get("matter").get("id")
        note_payload = {
            "externalMatterId": matter_external_id,
            # "externalLeadId": "string",
            "syncNotes": [
                {
                    "externalId": "string",
                    "body": "string",
                    "createdAt": "string",
                    "updatedAt": "string",
                    "title": "string",
                    "authorEmail": "string",
                    "authorName": "string",
                }
            ],
        }
        # response = self._request("POST", "/v1/notes/batch-sync", json=note_payload)
        # logging.info(f"Note sync response: {response.status_code} - {response.text}")
        return external_id

    def upload_invoice(self, matter_id: str, file_path: Path) -> UploadResult:
        external_doc_id = file_path.name
        mime_type = "application/pdf"

        docs_to_sync = [
            {
                "externalId": external_doc_id,
                "fileName": file_path.name,
                "mimeType": mime_type,
            }
        ]

        sync_response = self._request(
            "POST",
            "/v1/documents/batch-sync",
            json={"externalMatterId": matter_id, "syncDocuments": docs_to_sync},
        ).json()

        doc_result = sync_response["syncDocuments"][0]
        signed_url = doc_result.get("signedUploadUrl")

        if not signed_url:
            return UploadResult(
                status="skipped",
                message="No upload needed",
                document=doc_result["document"],
            )

        with open(file_path, "rb") as f:
            resp = requests.put(signed_url, data=f, headers={"Content-Type": mime_type})
            resp.raise_for_status()

        self._request(
            "POST",
            "/v1/documents/confirm-upload",
            json={
                "externalMatterId": matter_id,
                "externalDocumentIds": [external_doc_id],
            },
        )

        return UploadResult(status="uploaded", document=doc_result["document"])

    def list_matters(self) -> list[dict]:
        """Fetch all matters with pagination."""
        all_matters = []
        cursor = None

        while True:
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor

            response = self._request("GET", "/v1/matters", params=params)
            data = response.json()

            all_matters.extend(data.get("items", []))

            if not data.get("hasNext"):
                break
            cursor = data.get("nextCursor")

        return all_matters

    def get_matter_notes(self, matter_external_id: str) -> list[dict]:
        """Fetch all notes for a matter."""
        all_notes = []
        cursor = None

        while True:
            params = {"limit": 100, "externalMatterId": matter_external_id}
            if cursor:
                params["cursor"] = cursor

            try:
                response = self._request("GET", "/v1/notes", params=params)
                data = response.json()

                all_notes.extend(data.get("items", []))

                if not data.get("hasNext"):
                    break
                cursor = data.get("nextCursor")
            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    break
                raise

        return all_notes

    def get_matter_documents(self, matter_external_id: str) -> list[dict]:
        """Fetch all documents for a matter."""
        all_docs = []
        cursor = None

        while True:
            params = {"limit": 100, "externalMatterId": matter_external_id}
            if cursor:
                params["cursor"] = cursor

            try:
                response = self._request("GET", "/v1/documents", params=params)
                data = response.json()

                all_docs.extend(data.get("items", []))

                if not data.get("hasNext"):
                    break
                cursor = data.get("nextCursor")
            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    break
                raise

        return all_docs
