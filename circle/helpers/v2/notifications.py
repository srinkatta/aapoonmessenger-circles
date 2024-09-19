import firebase_admin
from firebase_admin import credentials, messaging, App
import logging
from circle_service import settings


class FirebaseNotificationService:
    def __init__(self) -> None:
        """
        Initializes the FirebaseNotificationService by setting the credential paths
        and initializing Firebase apps.
        """
        self.android_cred_path: str = settings.FCM_ADMIN_ANDROID_CRED
        self.ios_cred_path: str = settings.FCM_ADMIN_IOS_CRED
        self.android_app: App = None
        self.ios_app: App = None
        self._initialize_firebase_apps()

    def _initialize_firebase_apps(self) -> None:
        """
        Initializes the Firebase apps for Android and iOS, ensuring that each app is
        only initialized once by checking if an app with the given name already exists.
        """
        try:
            if not self._firebase_app_exists("android_app"):
                android_cred = credentials.Certificate(self.android_cred_path)
                self.android_app = firebase_admin.initialize_app(android_cred, name="android_app")
            else:
                self.android_app = firebase_admin.get_app(name="android_app")

            if not self._firebase_app_exists("ios_app"):
                ios_cred = credentials.Certificate(self.ios_cred_path)
                self.ios_app = firebase_admin.initialize_app(ios_cred, name="ios_app")
            else:
                self.ios_app = firebase_admin.get_app(name="ios_app")
        except Exception as e:
            logging.error(f"Failed to initialize Firebase apps: {e}")
            raise

    def _firebase_app_exists(self, app_name: str) -> bool:
        """
        Checks if a Firebase app with the given name already exists.

        Args:
            app_name (str): The name of the Firebase app to check.

        Returns:
            bool: True if the app exists, False otherwise.
        """
        try:
            firebase_admin.get_app(name=app_name)
            return True
        except ValueError:
            return False

    def send_android_notification(
        self,
        android_topic_name: str,
        title: str,
        message: str,
        sender_jid: str,
        bubble_type: str,
        data: dict,
        topic_name: str,
        message_id: str,
    ) -> str:
        """
        Sends a notification to an Android device.

        Args:
            android_topic_name (str): The topic name for the Android notification.
            title (str): The title of the notification.
            message (str): The message body of the notification.
            sender_jid (str): The sender JID.
            bubble_type (str): The type of bubble.
            data (dict): Additional data for the notification.
            topic_name (str): The topic name for the room.
            message_id (str): The message ID.

        Returns:
            str: The response from the Firebase messaging service.
        """
        data_message: dict = {
            "Nick": title,
            "body": message,
            "priority": "high",
            "sender_jid": sender_jid,
            "room_id": topic_name,
            "bubble_type": bubble_type,
            "data": data,
            "message_id": message_id,
        }

        print(f"Android data message: {data_message}")

        android_message: messaging.Message = messaging.Message(
            data=data_message,
            android=messaging.AndroidConfig(
                ttl=3600,  # time to live in seconds
                priority="high",
                notification=messaging.AndroidNotification(
                    title=title, body=message, icon="stock_ticker_update", color="#f45342"
                ),
            ),
            topic=android_topic_name,
        )
        print(f"Android notification message: {android_message}")

        try:
            response: str = messaging.send(android_message, app=self.android_app)
            logging.info(f"Successfully sent Android message: {response}")
            return response
        except Exception as e:
            logging.error(f"Failed to send Android notification: {e}")

    def send_ios_notification(
        self,
        ios_topic_name: str,
        title: str,
        message: str,
        sender_jid: str,
        bubble_type: str,
        data: dict,
        topic_name: str,
        message_id: str,
    ) -> str:
        """
        Sends a notification to an iOS device.

        Args:
            ios_topic_name (str): The topic name for the iOS notification.
            title (str): The title of the notification.
            message (str): The message body of the notification.
            sender_jid (str): The sender JID.
            bubble_type (str): The type of bubble.
            data (dict): Additional data for the notification.
            topic_name (str): The topic name for the room.
            message_id (str): The message ID.

        Returns:
            str: The response from the Firebase messaging service.
        """
        data_message = {
            "delivery_receipt_requested": True,
            "score": "Circle Notification",
            "sender_jid": sender_jid,
            "room_id": topic_name,
            "bubble_type": bubble_type,
            "data": data,
            "message_id": message_id,
            "mutable-content": 1,
            "content-available": True,
        }
        print(f"iOS data message: {data_message}")

        ios_message: messaging.Message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=message,
            ),
            android=messaging.AndroidConfig(
                priority="high",
            ),
            apns=messaging.APNSConfig(
                headers={
                    "apns-priority": "10",
                },
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        alert=messaging.ApsAlert(
                            title=title,
                            body=message,
                        ),
                        badge=0,
                        content_available=True,
                    ),
                    custom_data=data_message,
                ),
            ),
            topic=ios_topic_name,
        )
        print(f"iOS notification message: {ios_message}")

        try:
            response: str = messaging.send(ios_message, app=self.ios_app)
            logging.info(f"Successfully sent iOS message: {response}")
            return response
        except Exception as e:
            logging.error(f"Failed to send iOS notification: {e}")
