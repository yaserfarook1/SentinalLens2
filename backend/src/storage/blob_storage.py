"""
Azure Blob Storage Service for Report Persistence

Handles uploading, downloading, and managing audit reports in Azure Blob Storage.
Reports are stored with configurable expiration dates for lifecycle management.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from azure.storage.blob import BlobServiceClient, BlobClient, ContentSettings, generate_blob_sas, BlobSasPermissions
from azure.core.exceptions import AzureError, ResourceNotFoundError
from src.config import settings

logger = logging.getLogger(__name__)


class BlobStorageService:
    """
    Service for managing audit reports in Azure Blob Storage.

    Features:
    - Upload reports with metadata (job_id, workspace, timestamp)
    - Download reports as JSON/CSV/raw
    - List saved reports with metadata
    - Handle blob expiration and lifecycle
    - Error handling and logging
    """

    def __init__(self):
        """Initialize Blob Storage client."""
        self.connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
        self.account_name = settings.AZURE_STORAGE_ACCOUNT_NAME
        self.account_key = settings.AZURE_STORAGE_ACCOUNT_KEY
        self.container_name = settings.AZURE_STORAGE_CONTAINER_REPORTS
        self.expiration_days = settings.REPORT_EXPIRATION_DAYS

        # Build connection string if account name/key provided
        if not self.connection_string and self.account_name and self.account_key:
            self.connection_string = (
                f"DefaultEndpointsProtocol=https;"
                f"AccountName={self.account_name};"
                f"AccountKey={self.account_key};"
                f"EndpointSuffix=core.windows.net"
            )

        # Extract account name and key from connection string if not already set
        if self.connection_string:
            if not self.account_name:
                # Extract: AccountName=value from connection string
                parts = self.connection_string.split(";")
                for part in parts:
                    if part.startswith("AccountName="):
                        self.account_name = part.split("=", 1)[1]
                        break

            if not self.account_key:
                # Extract: AccountKey=value from connection string
                parts = self.connection_string.split(";")
                for part in parts:
                    if part.startswith("AccountKey="):
                        self.account_key = part.split("=", 1)[1]
                        break

        logger.info(
            f"[BLOB_STORAGE] Initialized with account: {self.account_name or 'UNKNOWN'}, "
            f"container: {self.container_name}, retention: {self.expiration_days}d"
        )

        self.client: Optional[BlobServiceClient] = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of blob client."""
        if self._initialized:
            return

        if not self.connection_string:
            logger.error(
                "[BLOB_STORAGE] No Azure Storage connection string configured. "
                "Set AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT_NAME + ACCOUNT_KEY"
            )
            raise RuntimeError(
                "Azure Storage not configured. "
                "Add to .env.local: AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT_NAME + ACCOUNT_KEY"
            )

        try:
            self.client = BlobServiceClient.from_connection_string(self.connection_string)
            logger.info(f"[BLOB_STORAGE] Initialized blob storage client for container: {self.container_name}")
            self._initialized = True
        except AzureError as e:
            logger.error(f"[BLOB_STORAGE] Failed to initialize: {e}")
            raise RuntimeError(f"Failed to initialize Blob Storage: {e}") from e

    def _get_container_client(self):
        """Get or create container client."""
        self._ensure_initialized()
        return self.client.get_container_client(self.container_name)

    async def upload_report(
        self,
        job_id: str,
        report_data: str,
        content_type: str = "application/json",
        metadata: Optional[dict] = None
    ) -> str:
        """
        Upload a report to blob storage.

        Args:
            job_id: Unique job identifier
            report_data: JSON/CSV string content
            content_type: MIME type (application/json, text/csv, text/plain)
            metadata: Optional dict with report metadata (workspace_name, timestamp, etc)

        Returns:
            Signed SAS URL with temporary read access (24 hours)
            No additional authentication needed - URL is self-contained

        Raises:
            RuntimeError: If upload fails
        """
        try:
            self._ensure_initialized()
            container_client = self._get_container_client()

            # Create container if it doesn't exist
            try:
                container_client.get_container_properties()
            except ResourceNotFoundError:
                logger.info(f"[BLOB_STORAGE] Creating container: {self.container_name}")
                container_client = self.client.create_container(self.container_name)

            # Generate blob name with timestamp and job_id
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            blob_name = f"reports/{job_id}/{timestamp}.json"

            # Upload blob with metadata
            blob_client = container_client.get_blob_client(blob_name)

            meta = metadata or {}
            meta.update({
                "job_id": job_id,
                "uploaded_at": datetime.utcnow().isoformat(),
                "content_type": content_type,
                "expiration_days": str(self.expiration_days),
            })

            blob_client.upload_blob(
                report_data,
                overwrite=True,
                metadata=meta,
                content_settings=ContentSettings(content_type=content_type)
            )

            # Generate SAS URL for temporary access (24 hours)
            blob_url_with_sas = self._generate_sas_url(blob_name)
            if not blob_url_with_sas:
                raise RuntimeError("Failed to generate SAS URL after upload")

            expires_at = (datetime.utcnow() + timedelta(days=self.expiration_days)).isoformat()

            logger.info(
                f"[BLOB_STORAGE] Report uploaded successfully: job_id={job_id} "
                f"blob_name={blob_name} sas_expires=24h storage_expires={expires_at}"
            )

            return blob_url_with_sas

        except Exception as e:
            logger.error(f"[BLOB_STORAGE] Upload failed: job_id={job_id}, error={e}")
            raise RuntimeError(f"Failed to upload report to blob storage: {e}") from e

    async def download_report(self, job_id: str) -> tuple[str, str]:
        """
        Download a report from blob storage.

        Args:
            job_id: Unique job identifier

        Returns:
            Tuple of (report_data, blob_url_with_sas)
            blob_url includes SAS token for temporary access (24 hours)

        Raises:
            ResourceNotFoundError: If report not found
            RuntimeError: If download fails
        """
        try:
            self._ensure_initialized()
            container_client = self._get_container_client()

            # List blobs with this job_id prefix
            blobs = list(container_client.list_blobs(name_starts_with=f"reports/{job_id}/"))

            if not blobs:
                raise ResourceNotFoundError(f"No reports found for job_id: {job_id}")

            # Get the most recent blob (last one by timestamp)
            latest_blob = max(blobs, key=lambda b: b.creation_time)
            blob_client = container_client.get_blob_client(latest_blob.name)

            # Download blob data
            download_stream = blob_client.download_blob()
            report_data = download_stream.readall().decode("utf-8")

            # Generate SAS URL for temporary access
            blob_url_with_sas = self._generate_sas_url(latest_blob.name)
            if not blob_url_with_sas:
                logger.warning(f"[BLOB_STORAGE] Failed to generate SAS URL, returning unsigned URL")
                blob_url_with_sas = blob_client.url

            logger.info(f"[BLOB_STORAGE] Report downloaded: job_id={job_id}, blob={latest_blob.name}")

            return report_data, blob_url_with_sas

        except ResourceNotFoundError:
            logger.warning(f"[BLOB_STORAGE] Report not found: job_id={job_id}")
            raise
        except Exception as e:
            logger.error(f"[BLOB_STORAGE] Download failed: job_id={job_id}, error={e}")
            raise RuntimeError(f"Failed to download report from blob storage: {e}") from e

    def _generate_sas_url(self, blob_name: str, hours: int = 24) -> Optional[str]:
        """
        Generate a SAS URL for a blob.

        Args:
            blob_name: Full blob path (e.g., reports/job-123/timestamp.json)
            hours: How many hours the SAS token is valid (default: 24)

        Returns:
            Signed URL with temporary access, or None if generation fails
        """
        try:
            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=self.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=hours)
            )
            base_url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}"
            return f"{base_url}?{sas_token}"
        except Exception as e:
            logger.warning(f"[BLOB_STORAGE] Failed to generate SAS URL for {blob_name}: {e}")
            return None

    async def list_saved_reports(self) -> list[dict]:
        """
        List all saved reports with metadata.

        Returns:
            List of dicts with blob metadata (name, job_id, created, expires_at, sas_url)
            sas_url includes temporary read access token (24 hours)
        """
        try:
            self._ensure_initialized()
            container_client = self._get_container_client()

            reports = []
            for blob in container_client.list_blobs():
                if blob.name.startswith("reports/"):
                    job_id = blob.name.split("/")[1]
                    expires_at = (
                        blob.creation_time + timedelta(days=self.expiration_days)
                    ).isoformat() if blob.creation_time else None

                    # Generate SAS URL for this report
                    sas_url = self._generate_sas_url(blob.name)

                    reports.append({
                        "blob_name": blob.name,
                        "job_id": job_id,
                        "created_at": blob.creation_time.isoformat() if blob.creation_time else None,
                        "expires_at": expires_at,
                        "size_bytes": blob.size,
                        "sas_url": sas_url,
                    })

            logger.info(f"[BLOB_STORAGE] Listed {len(reports)} saved reports with SAS URLs")
            return reports

        except Exception as e:
            logger.error(f"[BLOB_STORAGE] Failed to list reports: {e}")
            return []

    async def delete_report(self, job_id: str) -> bool:
        """
        Delete a report from blob storage.

        Args:
            job_id: Unique job identifier

        Returns:
            True if deleted, False if not found
        """
        try:
            self._ensure_initialized()
            container_client = self._get_container_client()

            blobs = list(container_client.list_blobs(name_starts_with=f"reports/{job_id}/"))
            if not blobs:
                logger.warning(f"[BLOB_STORAGE] No reports found to delete: job_id={job_id}")
                return False

            for blob in blobs:
                container_client.delete_blob(blob.name)
                logger.info(f"[BLOB_STORAGE] Deleted report: {blob.name}")

            return True

        except Exception as e:
            logger.error(f"[BLOB_STORAGE] Failed to delete report: job_id={job_id}, error={e}")
            return False


# Singleton instance
blob_storage_service = BlobStorageService()
