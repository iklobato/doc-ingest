import re
import requests
from pathlib import Path
from typing import Protocol

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
        self._request("PUT", f"/v1/matters/{external_id}", json=payload)
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
