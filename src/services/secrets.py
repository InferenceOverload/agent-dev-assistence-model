"""Secret Manager client for sensitive credentials."""

import logging
from typing import Optional
from google.cloud import secretmanager

logger = logging.getLogger(__name__)


class SecretsClient:
    """Client for Google Secret Manager."""
    
    def __init__(self, project: str):
        self.project = project
        self.client = secretmanager.SecretManagerServiceClient()
        
    def get_secret(self, secret_id: str, version: str = "latest") -> Optional[str]:
        """Retrieve a secret value.
        
        Args:
            secret_id: Secret identifier
            version: Secret version (default: latest)
        
        Returns:
            Secret value or None if not found
        """
        try:
            name = f"projects/{self.project}/secrets/{secret_id}/versions/{version}"
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            logger.error(f"Failed to retrieve secret {secret_id}: {e}")
            return None
            
    def create_secret(self, secret_id: str, secret_value: str) -> bool:
        """Create a new secret.
        
        Args:
            secret_id: Secret identifier
            secret_value: Secret value
        
        Returns:
            Success status
        """
        try:
            parent = f"projects/{self.project}"
            
            # Create the secret
            secret = self.client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": {"replication": {"automatic": {}}}
                }
            )
            
            # Add secret version
            self.client.add_secret_version(
                request={
                    "parent": secret.name,
                    "payload": {"data": secret_value.encode("UTF-8")}
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create secret {secret_id}: {e}")
            return False