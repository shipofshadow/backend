"""S3 Storage Service for backup management"""
import os
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from config import Config


class S3Service:
    """Service class for S3 operations"""

    def __init__(self):
        self.enabled = Config.S3_ENABLED
        self.bucket = Config.S3_BUCKET
        self._client = None

    @property
    def client(self):
        """Lazy-load S3 client"""
        if self._client is None and self.enabled:
            endpoint_url = Config.S3_ENDPOINT if Config.S3_ENDPOINT else None
            self._client = boto3.client(
                "s3",
                aws_access_key_id=Config.S3_ACCESS_KEY,
                aws_secret_access_key=Config.S3_SECRET_KEY,
                region_name=Config.S3_REGION,
                endpoint_url=endpoint_url
            )
        return self._client

    def upload_file(self, local_path: str, s3_key: str) -> bool:
        """Upload a file to S3"""
        if not self.enabled:
            raise RuntimeError("S3 is not enabled")
        if not self.client:
            raise RuntimeError("S3 client not initialized")

        try:
            self.client.upload_file(local_path, self.bucket, s3_key)
            return True
        except ClientError as e:
            print(f"S3 upload error: {e}")
            raise

    def download_file(self, s3_key: str, local_path: str) -> bool:
        """Download a file from S3"""
        if not self.enabled:
            raise RuntimeError("S3 is not enabled")
        if not self.client:
            raise RuntimeError("S3 client not initialized")

        try:
            self.client.download_file(self.bucket, s3_key, local_path)
            return True
        except ClientError as e:
            print(f"S3 download error: {e}")
            raise

    def delete_file(self, s3_key: str) -> bool:
        """Delete a file from S3"""
        if not self.enabled:
            raise RuntimeError("S3 is not enabled")
        if not self.client:
            raise RuntimeError("S3 client not initialized")

        try:
            self.client.delete_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError as e:
            print(f"S3 delete error: {e}")
            raise

    def list_files(self, prefix: str = "backups/") -> list:
        """List files in S3 bucket with given prefix"""
        if not self.enabled:
            raise RuntimeError("S3 is not enabled")
        if not self.client:
            raise RuntimeError("S3 client not initialized")

        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix
            )
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'filename': os.path.basename(obj['Key']),
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat()
                })
            return files
        except ClientError as e:
            print(f"S3 list error: {e}")
            raise

    def file_exists(self, s3_key: str) -> bool:
        """Check if a file exists in S3"""
        if not self.enabled:
            return False
        if not self.client:
            return False

        try:
            self.client.head_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError:
            return False

    def get_file_info(self, s3_key: str) -> Optional[dict]:
        """Get file metadata from S3"""
        if not self.enabled:
            return None
        if not self.client:
            return None

        try:
            response = self.client.head_object(Bucket=self.bucket, Key=s3_key)
            return {
                'key': s3_key,
                'size': response['ContentLength'],
                'last_modified': response['LastModified'].isoformat(),
                'content_type': response.get('ContentType', 'application/octet-stream')
            }
        except ClientError:
            return None


# Singleton instance
s3_service = S3Service()
