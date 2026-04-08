import os
import threading
import logging
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from flask import current_app
from dotenv import load_dotenv

load_dotenv()

# Configure logger
logger = logging.getLogger(__name__)


class EmailClient:
    """Configures Brevo email client for sending emails"""
    
    def __init__(self):
        self.api_key = os.environ.get('BREVO_API_KEY')
        if not self.api_key:
            logger.error("BREVO_API_KEY environment variable not set")
            # TODO: Handle this error
            return
            
            
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = self.api_key
        proxy = (
            os.environ.get('HTTP_PROXY')
        )
        if proxy:
            configuration.proxy = proxy  # type: ignore[assignment]
            logger.info("EmailClient: using proxy %s", proxy)
        self.api_client = sib_api_v3_sdk.ApiClient(configuration)
        self.api_instance = sib_api_v3_sdk.TransactionalEmailsApi(self.api_client)
        logger.info("EmailClient initialized successfully")
    
    def _validate_emails(self, to_emails):
        """Validate email addresses"""
        if not to_emails:
            logger.error("Email addresses are required")
            return False

        if isinstance(to_emails, str):
            to_emails = [to_emails]
        
        # Validate each email address
        for email in to_emails:
            if not email or not email.strip():
                logger.error(f"Invalid email address: {email}")
                return False
            if '@' not in email or '.' not in email:
                logger.error(f"Invalid email format: {email}")
                return False
        
        return to_emails
    
    def _create_email_message(self, to_emails, subject, html_content=None, 
                             text_content=None):
        """Create email message object"""
        try:
            message = sib_api_v3_sdk.SendSmtpEmail(
                to=[{"email": email.strip()} for email in to_emails],
                sender={"email": "forghani.dev@gmail.com", "name": "ClientEase"},
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            return message
        except Exception as e:
            logger.error(f"Failed to create email message: {e}")
            return None
    
    def _send_email_sync(self, message):
        """Send email synchronously"""
        try:
            response = self.api_instance.send_transac_email(message)
            message_id = getattr(response, "message_id", None)
            if message_id:
                logger.info(
                    f"Email sent successfully. Message ID: {message_id}"
                )
            else:
                logger.info("Email sent successfully. No message ID returned.")
            return True
        except ApiException as e:
            logger.error(f"API error sending email: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False
    
    def _send_email_async(self, message):
        """Send email asynchronously in background thread"""
        try:
            response = self.api_instance.send_transac_email(message)
            message_id = getattr(response, "message_id", None)
            if message_id:
                logger.info(
                    f"Email sent asynchronously. Message ID: {message_id}"
                )
            else:
                logger.info("Email sent asynchronously. No message ID returned.")
        except ApiException as e:
            logger.error(f"API error sending email asynchronously: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending email asynchronously: {e}")
    
    def send_email(self, to_emails, subject, html_content=None, text_content=None, 
                   sync=False):
        """
        Send email to the given email addresses
        
        Args:
            to_emails: Single email string or list of email strings
            subject: Email subject
            html_content: HTML content of the email (optional)
            text_content: Plain text content of the email (optional)
            sync: If True, send synchronously. If False (default), send asynchronously
        
        Returns:
            bool: True if email was queued/sent successfully, False otherwise
        """
        logger.info(f"Preparing to send email to: {to_emails}, subject: {subject}")
        
        # Validate email addresses
        validated_emails = self._validate_emails(to_emails)
        if not validated_emails:
            return False
        
        # Create email message
        message = self._create_email_message(validated_emails, subject, 
                                           html_content, text_content)
        if not message:
            return False
        
        if sync:
            # Synchronous sending (for critical emails that must be sent immediately)
            logger.info("Sending email synchronously")
            return self._send_email_sync(message)
        else:
            # Asynchronous sending (default behavior)
            logger.info("Queueing email for asynchronous sending")
            try:
                # Start email sending in background thread
                thread = threading.Thread(
                    target=self._send_email_async,
                    args=(message,)
                )
                thread.daemon = True
                thread.start()
                
                logger.info("Email queued for async sending successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to queue email for async sending: {e}")
                return False
    
    def send_email_test(self):
        """Send a test email"""
        logger.info("Sending test email")
        return self.send_email(
            to_emails='forghanip99@gmail.com',
            subject='Test Email',
            text_content='This is a test email from ClientEase'
        )


# Create global instance
email_client = EmailClient()
