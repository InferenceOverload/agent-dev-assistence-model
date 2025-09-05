"""Tests for workspace storage abstraction."""

import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from src.services.workspace_storage import (
    LocalWorkspaceStorage, 
    WorkspaceStorageFactory,
    configure_workspace_storage,
    get_workspace_storage
)


class TestLocalWorkspaceStorage:
    """Tests for local filesystem storage."""
    
    def test_local_storage_init(self, tmp_path):
        """Test local storage initialization."""
        storage = LocalWorkspaceStorage(str(tmp_path / "workspace"))
        assert storage.root_dir.exists()
        assert "workspace" in str(storage.root_dir)
    
    def test_local_storage_makedirs(self, tmp_path):
        """Test creating directories."""
        storage = LocalWorkspaceStorage(str(tmp_path / "workspace"))
        storage.makedirs("repos/test-repo")
        
        expected_path = storage.root_dir / "repos" / "test-repo"
        assert expected_path.exists()
        assert expected_path.is_dir()
    
    def test_local_storage_exists(self, tmp_path):
        """Test checking if path exists."""
        storage = LocalWorkspaceStorage(str(tmp_path / "workspace"))
        
        # Initially doesn't exist
        assert not storage.exists("repos/test-repo")
        
        # Create and check again
        storage.makedirs("repos/test-repo")
        assert storage.exists("repos/test-repo")
    
    def test_local_storage_get_local_path(self, tmp_path):
        """Test getting local path."""
        storage = LocalWorkspaceStorage(str(tmp_path / "workspace"))
        local_path = storage.get_local_path("repos/test-repo")
        
        assert Path(local_path).is_absolute()
        assert "repos" in local_path
        assert "test-repo" in local_path
    
    def test_local_storage_sync(self, tmp_path):
        """Test syncing to storage."""
        storage = LocalWorkspaceStorage(str(tmp_path / "workspace"))
        
        # Create a source directory with a file
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "test.txt").write_text("test content")
        
        # Sync to storage
        storage.sync_to_storage(str(source_dir), "repos/synced")
        
        # Verify synced
        synced_path = storage.root_dir / "repos" / "synced"
        assert synced_path.exists()
        assert (synced_path / "test.txt").read_text() == "test content"


class TestWorkspaceStorageFactory:
    """Tests for storage factory."""
    
    def test_factory_default_local(self):
        """Test factory creates local storage by default."""
        storage = WorkspaceStorageFactory.create()
        assert isinstance(storage, LocalWorkspaceStorage)
    
    def test_factory_with_config(self, tmp_path):
        """Test factory with explicit config."""
        config = {
            "storage_type": "local",
            "local_root": str(tmp_path / "custom")
        }
        storage = WorkspaceStorageFactory.create(config)
        
        assert isinstance(storage, LocalWorkspaceStorage)
        assert "custom" in str(storage.root_dir)
    
    @patch.dict(os.environ, {"ADAM_STORAGE_TYPE": "local", "ADAM_WORKSPACE_ROOT": "/tmp/test"})
    def test_factory_env_vars(self):
        """Test factory reads environment variables."""
        storage = WorkspaceStorageFactory.create()
        assert isinstance(storage, LocalWorkspaceStorage)
        assert storage.root_dir == Path("/tmp/test").resolve()
    
    @patch.dict(os.environ, {"K_SERVICE": "test-service"})
    def test_factory_cloud_environment(self):
        """Test factory uses /tmp in cloud environments."""
        storage = WorkspaceStorageFactory.create()
        assert isinstance(storage, LocalWorkspaceStorage)
        # On macOS, /tmp resolves to /private/tmp
        assert "/tmp" in str(storage.root_dir) or "/private/tmp" in str(storage.root_dir)
    
    @patch.dict(os.environ, {"ADAM_STORAGE_TYPE": "gcs", "ADAM_GCS_BUCKET": ""})
    def test_factory_gcs_fallback(self):
        """Test factory falls back to local if GCS not configured."""
        with patch('src.services.workspace_storage.logger') as mock_logger:
            storage = WorkspaceStorageFactory.create()
            assert isinstance(storage, LocalWorkspaceStorage)
            mock_logger.warning.assert_called_once()


class TestGCSWorkspaceStorage:
    """Tests for GCS storage (mocked)."""
    
    def test_gcs_init_mock(self):
        """Test GCS storage initialization with fully mocked client."""
        # Mock the entire google.cloud.storage module
        mock_storage = MagicMock()
        mock_client = Mock()
        mock_bucket = Mock()
        mock_client.bucket.return_value = mock_bucket
        mock_storage.Client.return_value = mock_client
        
        with patch.dict('sys.modules', {'google.cloud.storage': mock_storage}):
            # Need to reload the module to pick up the mock
            import importlib
            import src.services.workspace_storage
            importlib.reload(src.services.workspace_storage)
            from src.services.workspace_storage import GCSWorkspaceStorage
            
            storage = GCSWorkspaceStorage("test-bucket", "workspace")
            assert storage.bucket_name == "test-bucket"
            assert storage.prefix == "workspace"
            mock_client.bucket.assert_called_once_with("test-bucket")
    
    def test_gcs_import_error(self):
        """Test GCS storage raises error when libraries not available."""
        with patch.dict('sys.modules', {'google.cloud.storage': None}):
            from src.services.workspace_storage import GCSWorkspaceStorage
            
            with pytest.raises(ImportError, match="Google Cloud Storage libraries"):
                GCSWorkspaceStorage("test-bucket")


class TestIntegration:
    """Integration tests for workspace storage with repo_io."""
    
    def test_clone_repo_with_local_storage(self, tmp_path, monkeypatch):
        """Test clone_repo uses workspace storage."""
        # Configure local storage
        config = {
            "storage_type": "local",
            "local_root": str(tmp_path / "workspace")
        }
        configure_workspace_storage(config)
        
        # Create a mock git repo
        mock_repo = tmp_path / "mock-repo"
        mock_repo.mkdir()
        (mock_repo / ".git").mkdir()
        (mock_repo / "README.md").write_text("Test repo")
        
        # Mock subprocess to avoid actual git clone
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            
            from src.tools.repo_io import clone_repo
            
            # Use file:// URL
            result = clone_repo(f"file://{mock_repo}")
            
            # Verify it uses the configured workspace
            assert "workspace" in result
            assert "repos" in result
            
            # Verify git clone was called
            mock_run.assert_called()
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "git"
            assert call_args[1] == "clone"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])