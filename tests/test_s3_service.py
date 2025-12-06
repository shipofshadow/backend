"""Tests for S3Service functionality."""

import pytest
from unittest.mock import patch, MagicMock
import sys


class MockConfig:
    """Mock Config class for testing."""
    S3_ENABLED = False
    S3_BUCKET = "test-bucket"
    S3_ACCESS_KEY = "test-key"
    S3_SECRET_KEY = "test-secret"
    S3_REGION = "us-east-1"
    S3_ENDPOINT = None


# Patch the config module before importing S3Service
@pytest.fixture(autouse=True)
def mock_config_module():
    """Mock the config module for all tests."""
    mock_config = MagicMock()
    mock_config.Config = MockConfig
    sys.modules['config'] = mock_config
    yield mock_config
    if 'services.s3_service' in sys.modules:
        del sys.modules['services.s3_service']
    if 'config' in sys.modules:
        del sys.modules['config']


class TestS3ServiceGetS3Key:
    """Test the get_s3_key method."""

    def test_get_s3_key_adds_uploads_prefix(self, mock_config_module):
        """Test that get_s3_key adds uploads/ prefix to filenames."""
        from services.s3_service import S3Service
        service = S3Service()
        
        result = service.get_s3_key("test_file.jpg")
        assert result == "uploads/test_file.jpg"

    def test_get_s3_key_preserves_existing_uploads_prefix(self, mock_config_module):
        """Test that get_s3_key doesn't double-prefix."""
        from services.s3_service import S3Service
        service = S3Service()
        
        result = service.get_s3_key("uploads/test_file.jpg")
        assert result == "uploads/test_file.jpg"

    def test_get_s3_key_with_backups_prefix(self, mock_config_module):
        """Test that get_s3_key supports backups prefix."""
        from services.s3_service import S3Service
        service = S3Service()
        
        result = service.get_s3_key("backup_2024.sql.gz", prefix="backups")
        assert result == "backups/backup_2024.sql.gz"

    def test_get_s3_key_preserves_existing_backups_prefix(self, mock_config_module):
        """Test that get_s3_key doesn't double-prefix for backups."""
        from services.s3_service import S3Service
        service = S3Service()
        
        result = service.get_s3_key("backups/backup_2024.sql.gz", prefix="backups")
        assert result == "backups/backup_2024.sql.gz"


class TestS3ServiceUploadFileWithContentType:
    """Test the upload_file_with_content_type method."""

    def test_upload_file_returns_none_when_disabled(self, mock_config_module):
        """Test that upload returns None when S3 is disabled."""
        MockConfig.S3_ENABLED = False
        
        from services.s3_service import S3Service
        service = S3Service()
        
        result = service.upload_file_with_content_type("/path/to/file.jpg", "file.jpg")
        assert result is None

    def test_upload_file_returns_s3_key_on_success(self, mock_config_module):
        """Test that upload returns the S3 key on success."""
        MockConfig.S3_ENABLED = True
        
        from services.s3_service import S3Service
        service = S3Service()
        service._client = MagicMock()
        service._client.upload_file = MagicMock()
        
        result = service.upload_file_with_content_type("/path/to/file.jpg", "file.jpg")
        assert result == "uploads/file.jpg"


class TestS3ServiceGeneratePresignedUrl:
    """Test the generate_presigned_url method."""

    def test_generate_presigned_url_raises_when_disabled(self, mock_config_module):
        """Test that generate_presigned_url raises when S3 is disabled."""
        MockConfig.S3_ENABLED = False
        
        from services.s3_service import S3Service
        service = S3Service()
        
        with pytest.raises(RuntimeError, match="S3 is not enabled"):
            service.generate_presigned_url("uploads/test_file.jpg")

    def test_generate_presigned_url_returns_url(self, mock_config_module):
        """Test that generate_presigned_url returns a URL when S3 is enabled."""
        MockConfig.S3_ENABLED = True
        
        from services.s3_service import S3Service
        service = S3Service()
        service._client = MagicMock()
        service._client.generate_presigned_url = MagicMock(return_value="https://example.com/presigned")
        
        result = service.generate_presigned_url("uploads/test_file.jpg")
        assert result == "https://example.com/presigned"
        
        # Verify the correct parameters were passed
        service._client.generate_presigned_url.assert_called_once_with(
            ClientMethod='get_object',
            Params={'Bucket': 'test-bucket', 'Key': 'uploads/test_file.jpg'},
            ExpiresIn=3600
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
