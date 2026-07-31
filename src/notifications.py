import os
import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger("TradingSystemNotifications")

class NotificationClient:
    def __init__(self):
        self.email_address = os.environ.get("NOTIFICATION_EMAIL")
        self.phone_country = os.environ.get("NOTIFICATION_PH_COUNTRY", "+1")
        self.phone_number = os.environ.get("NOTIFICATION_PHONE")
        
        # We rely on boto3 picking up the IAM role from the EC2 instance
        self.sns_client = boto3.client('sns', region_name='us-east-1')
        self.ses_client = boto3.client('ses', region_name='us-east-1')
        
    def send_brainstorm_alert(self, subject: str, message: str):
        if self.email_address:
            self._send_email(subject, message)
        
        if self.phone_number:
            # SMS messages are typically limited in length, so we send a summary pointer
            sms_body = f"Intelligent Invest Alert: {subject}\n\nCheck your email for the full brainstorming report!"
            self._send_sms(sms_body)

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

    def _send_sms(self, message: str):
        try:
            # Strip any weird characters and construct E.164 format
            clean_country = self.phone_country.replace("+", "").strip()
            clean_phone = self.phone_number.replace("-", "").replace(" ", "").strip()
            
            phone = f"+{clean_country}{clean_phone}"
            
            response = self.sns_client.publish(
                PhoneNumber=phone,
                Message=message
            )
            logger.info(f"SMS sent successfully to {phone}. Message ID: {response['MessageId']}")
        except ClientError as e:
            logger.error(f"Failed to send SMS: {e.response['Error']['Message']}")
            logger.warning("Ensure that your AWS account has sufficient SNS SMS quota/sandbox permissions.")
