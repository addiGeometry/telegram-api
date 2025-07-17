import hmac
import hashlib
import logging
from typing import Optional
from app.utils.config import settings

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Custom exception for authentication failures."""
    pass


class AuthService:
    """Service for handling Telegram webhook authentication and user authorization."""
    
    def __init__(self):
        self.allowed_user_ids = settings.allowed_user_ids_list
        self.shared_secret = settings.shared_secret
        self.telegram_token = settings.telegram_token
    
    def verify_telegram_webhook(self, token: str, update_data: str) -> bool:
        """
        Verify that the webhook request is authentic using Telegram's webhook secret.
        
        Args:
            token: The X-Telegram-Bot-Api-Secret-Token header value
            update_data: The raw JSON payload from the request
            
        Returns:
            bool: True if the webhook is authentic, False otherwise
        """
        try:
            # Create HMAC signature using the shared secret
            expected_signature = hmac.new(
                key=self.shared_secret.encode('utf-8'),
                msg=update_data.encode('utf-8'),
                digestmod=hashlib.sha256
            ).hexdigest()
            
            # Compare with the provided token
            return hmac.compare_digest(expected_signature, token)
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    def is_user_authorized(self, user_id: int) -> bool:
        """
        Check if a user is authorized to use the bot.
        
        Args:
            user_id: The Telegram user ID
            
        Returns:
            bool: True if the user is authorized, False otherwise
        """
        is_authorized = user_id in self.allowed_user_ids
        
        if not is_authorized:
            logger.warning(f"Unauthorized user attempted to use bot: {user_id}")
        
        return is_authorized
    
    def authenticate_request(self, token: Optional[str], update_data: str, user_id: int) -> bool:
        """
        Perform full authentication check including webhook verification and user authorization.
        
        Args:
            token: The X-Telegram-Bot-Api-Secret-Token header value
            update_data: The raw JSON payload from the request
            user_id: The Telegram user ID from the message
            
        Returns:
            bool: True if the request is fully authenticated, False otherwise
            
        Raises:
            AuthenticationError: If authentication fails with detailed error message
        """
        # Verify webhook authenticity
        if not token:
            raise AuthenticationError("Missing webhook secret token")
        
        if not self.verify_telegram_webhook(token, update_data):
            raise AuthenticationError("Invalid webhook signature")
        
        # Check user authorization
        if not self.is_user_authorized(user_id):
            raise AuthenticationError(f"User {user_id} is not authorized to use this bot")
        
        logger.info(f"Authentication successful for user {user_id}")
        return True


auth_service = AuthService()