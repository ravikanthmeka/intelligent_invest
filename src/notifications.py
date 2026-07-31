import os
import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger("TradingSystemNotifications")

class NotificationClient:
    def __init__(self):
        self.email_address = os.environ.get("NOTIFICATION_EMAIL")
        
        # We rely on boto3 picking up the IAM role from the EC2 instance
        self.ses_client = boto3.client('ses', region_name='us-east-1')
        
    def send_brainstorm_alert(self, subject: str, message: str):
        if self.email_address:
            self._send_email(subject, message)

    def _send_email(self, subject: str, body: str):
        try:
            response = self.ses_client.send_email(
                Destination={
                    'ToAddresses': [self.email_address]
                },
                Message={
                    'Body': {
                        'Text': {
                            'Charset': "UTF-8",
                            'Data': body
                        }
                    },
                    'Subject': {
                        'Charset': "UTF-8",
                        'Data': subject
                    },
                },
                Source=self.email_address # Assumption: The recipient email is verified in SES as a sender identity
            )
            logger.info(f"Email sent successfully. Message ID: {response['MessageId']}")
        except ClientError as e:
            logger.error(f"Failed to send email: {e.response['Error']['Message']}")
            logger.warning("Ensure that your NOTIFICATION_EMAIL is verified in AWS SES to send emails.")
