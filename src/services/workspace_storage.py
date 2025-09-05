"""Workspace storage abstraction for local filesystem and GCS.

Provides a configurable storage backend for cloned repositories and workspace files.
Supports both local filesystem and Google Cloud Storage.
"""

import os
import pathlib
import shutil
import tempfile
from typing import Optional, Union, BinaryIO
from abc import ABC, abstractmethod

from src.core.logging import get_logger

logger = get_logger(__name__)


class WorkspaceStorage(ABC):
    """Abstract base class for workspace storage backends."""
    
    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if a path exists in storage."""
        pass
    
    @abstractmethod
    def makedirs(self, path: str) -> None:
        """Create directory structure."""
        pass
    
    @abstractmethod
    def get_local_path(self, path: str) -> str:
        """Get a local filesystem path for operations like git clone.
        
        For local storage, returns the path directly.
        For cloud storage, downloads to temp and returns temp path.
        """
        pass
    
    @abstractmethod
    def sync_to_storage(self, local_path: str, storage_path: str) -> None:
        """Sync a local directory to storage.
        
        For local storage, this is a no-op if paths are the same.
        For cloud storage, uploads the directory.
        """
        pass
    
    @abstractmethod
    def cleanup_temp(self, temp_path: str) -> None:
        """Clean up temporary files if any."""
        pass


class LocalWorkspaceStorage(WorkspaceStorage):
    """Local filesystem storage backend."""
    
    def __init__(self, root_dir: str = ".workspace"):
        """Initialize local storage.
        
        Args:
            root_dir: Root directory for workspace storage
        """
        self.root_dir = pathlib.Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using local workspace storage at: {self.root_dir}")
    
    def exists(self, path: str) -> bool:
        """Check if a path exists locally."""
        full_path = self.root_dir / path
        return full_path.exists()
    
    def makedirs(self, path: str) -> None:
        """Create directory structure locally."""
        full_path = self.root_dir / path
        full_path.mkdir(parents=True, exist_ok=True)
    
    def get_local_path(self, path: str) -> str:
        """Return the local path directly."""
        full_path = self.root_dir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        return str(full_path)
    
    def sync_to_storage(self, local_path: str, storage_path: str) -> None:
        """No-op for local storage if paths match."""
        full_storage_path = self.root_dir / storage_path
        if pathlib.Path(local_path).resolve() != full_storage_path.resolve():
            # Copy if different locations
            if full_storage_path.exists():
                shutil.rmtree(full_storage_path)
            shutil.copytree(local_path, full_storage_path)
    
    def cleanup_temp(self, temp_path: str) -> None:
        """No cleanup needed for local storage."""
        pass


class GCSWorkspaceStorage(WorkspaceStorage):
    """Google Cloud Storage backend for workspace."""
    
    def __init__(self, bucket_name: str, prefix: str = "workspace"):
        """Initialize GCS storage.
        
        Args:
            bucket_name: GCS bucket name
            prefix: Prefix for all workspace objects in the bucket
        """
        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip('/')
        self.temp_dir = pathlib.Path(tempfile.gettempdir()) / "adam_workspace_temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Lazy import to avoid requiring GCS libraries when not used
        try:
            from google.cloud import storage
            self.storage_client = storage.Client()
            self.bucket = self.storage_client.bucket(bucket_name)
            logger.info(f"Using GCS workspace storage: gs://{bucket_name}/{prefix}")
        except ImportError:
            raise ImportError(
                "Google Cloud Storage libraries not installed. "
                "Install with: pip install google-cloud-storage"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize GCS client: {e}")
    
    def exists(self, path: str) -> bool:
        """Check if a path exists in GCS."""
        blob_prefix = f"{self.prefix}/{path}".rstrip('/')
        blobs = self.bucket.list_blobs(prefix=blob_prefix, max_results=1)
        return any(blobs)
    
    def makedirs(self, path: str) -> None:
        """Create a marker file for directory in GCS."""
        # GCS doesn't have real directories, but we can create a marker
        blob_path = f"{self.prefix}/{path}/.keep"
        blob = self.bucket.blob(blob_path)
        if not blob.exists():
            blob.upload_from_string("")
    
    def get_local_path(self, path: str) -> str:
        """Download from GCS to temp directory and return local path."""
        local_path = self.temp_dir / path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if already downloaded
        if local_path.exists():
            logger.debug(f"Using cached temp path: {local_path}")
            return str(local_path)
        
        # Download from GCS if exists
        blob_prefix = f"{self.prefix}/{path}"
        if self.exists(path):
            logger.info(f"Downloading from GCS: gs://{self.bucket_name}/{blob_prefix}")
            self._download_directory(blob_prefix, local_path)
        
        return str(local_path)
    
    def sync_to_storage(self, local_path: str, storage_path: str) -> None:
        """Upload a local directory to GCS."""
        blob_prefix = f"{self.prefix}/{storage_path}"
        logger.info(f"Uploading to GCS: {local_path} -> gs://{self.bucket_name}/{blob_prefix}")
        self._upload_directory(local_path, blob_prefix)
    
    def cleanup_temp(self, temp_path: str) -> None:
        """Clean up temporary downloaded files."""
        if temp_path.startswith(str(self.temp_dir)):
            try:
                shutil.rmtree(temp_path)
                logger.debug(f"Cleaned up temp path: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp path {temp_path}: {e}")
    
    def _download_directory(self, blob_prefix: str, local_dir: pathlib.Path) -> None:
        """Download all blobs with prefix to local directory."""
        blobs = self.bucket.list_blobs(prefix=blob_prefix)
        for blob in blobs:
            if blob.name.endswith('/'):
                continue  # Skip directory markers
            
            # Calculate relative path
            relative_path = blob.name[len(blob_prefix):].lstrip('/')
            if not relative_path:
                continue
                
            local_file = local_dir / relative_path
            local_file.parent.mkdir(parents=True, exist_ok=True)
            
            blob.download_to_filename(str(local_file))
            logger.debug(f"Downloaded: {blob.name} -> {local_file}")
    
    def _upload_directory(self, local_dir: str, blob_prefix: str) -> None:
        """Upload a local directory to GCS."""
        local_path = pathlib.Path(local_dir)
        
        for file_path in local_path.rglob('*'):
            if file_path.is_dir():
                continue
            
            relative_path = file_path.relative_to(local_path)
            blob_name = f"{blob_prefix}/{relative_path}".replace('\\', '/')
            
            blob = self.bucket.blob(blob_name)
            blob.upload_from_filename(str(file_path))
            logger.debug(f"Uploaded: {file_path} -> {blob_name}")


class WorkspaceStorageFactory:
    """Factory for creating workspace storage instances."""
    
    @staticmethod
    def create(config: Optional[dict] = None) -> WorkspaceStorage:
        """Create a workspace storage instance based on configuration.
        
        Args:
            config: Optional configuration dict with:
                - storage_type: "local" or "gcs"
                - local_root: Root directory for local storage
                - gcs_bucket: Bucket name for GCS storage
                - gcs_prefix: Prefix for GCS storage
        
        Returns:
            WorkspaceStorage instance
        """
        if config is None:
            config = {}
        
        # Check environment variables
        storage_type = config.get("storage_type") or os.getenv("ADAM_STORAGE_TYPE", "local")
        
        if storage_type == "gcs":
            bucket_name = config.get("gcs_bucket") or os.getenv("ADAM_GCS_BUCKET")
            if not bucket_name:
                logger.warning("GCS bucket not configured, falling back to local storage")
                storage_type = "local"
            else:
                prefix = config.get("gcs_prefix") or os.getenv("ADAM_GCS_PREFIX", "workspace")
                return GCSWorkspaceStorage(bucket_name, prefix)
        
        # Default to local storage
        local_root = config.get("local_root") or os.getenv("ADAM_WORKSPACE_ROOT", ".workspace")
        
        # Use /tmp for cloud environments if not explicitly configured
        if not config.get("local_root") and not os.getenv("ADAM_WORKSPACE_ROOT"):
            if os.getenv("K_SERVICE") or os.getenv("VERTEX_AI_ENDPOINT_ID"):
                local_root = "/tmp/adam_workspace"
        
        return LocalWorkspaceStorage(local_root)


# Global instance
_workspace_storage: Optional[WorkspaceStorage] = None


def get_workspace_storage() -> WorkspaceStorage:
    """Get or create the workspace storage singleton."""
    global _workspace_storage
    if _workspace_storage is None:
        _workspace_storage = WorkspaceStorageFactory.create()
    return _workspace_storage


def configure_workspace_storage(config: dict) -> None:
    """Configure workspace storage with specific settings.
    
    Args:
        config: Configuration dict with storage settings
    """
    global _workspace_storage
    _workspace_storage = WorkspaceStorageFactory.create(config)