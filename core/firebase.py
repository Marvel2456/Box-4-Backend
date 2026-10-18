import os
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

_firebase_initialized = False

def get_firebase_app():
    """
    Initializes and returns the Firebase Admin app singleton.
    Loads credentials from FIREBASE_CREDENTIALS_JSON (env string) or FIREBASE_CREDENTIALS_PATH (file path).
    """
    global _firebase_initialized
    try:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            cred_json_str = getattr(settings, 'FIREBASE_CREDENTIALS_JSON', None) or os.getenv('FIREBASE_CREDENTIALS_JSON')
            cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None) or os.getenv('FIREBASE_CREDENTIALS_PATH')

            cred = None
            if cred_json_str:
                try:
                    cred_dict = json.loads(cred_json_str)
                    cred = credentials.Certificate(cred_dict)
                except Exception as e:
                    logger.warning(f"[Firebase Init Warning] Failed to parse FIREBASE_CREDENTIALS_JSON: {e}")
            elif cred_path and os.path.exists(cred_path):
                try:
                    cred = credentials.Certificate(cred_path)
                except Exception as e:
                    logger.warning(f"[Firebase Init Warning] Failed to load credentials from {cred_path}: {e}")

            # Auto-discovery in project's firebase/ directory
            if not cred:
                firebase_dir = os.path.join(settings.BASE_DIR, 'firebase')
                if os.path.exists(firebase_dir):
                    has_client_file_only = False
                    for fname in sorted(os.listdir(firebase_dir)):
                        if fname.endswith('.json'):
                            fpath = os.path.join(firebase_dir, fname)
                            try:
                                with open(fpath, 'r', encoding='utf-8') as f:
                                    content = json.load(f)
                                if isinstance(content, dict):
                                    if content.get('type') == 'service_account':
                                        cred = credentials.Certificate(content)
                                        logger.info(f"[Firebase] Auto-discovered service account credentials at {fpath}")
                                        break
                                    elif 'project_info' in content and 'client' in content:
                                        has_client_file_only = True
                            except Exception as e:
                                logger.debug(f"[Firebase] Skipping {fname}: {e}")

                    if not cred and has_client_file_only:
                        logger.warning(
                            "[Firebase Config Notice] Found 'google-services.json' in firebase/ directory. "
                            "Note: 'google-services.json' is the client-side configuration for the mobile app (Android/Flutter). "
                            "To enable backend push notifications, please download the Service Account private key JSON from "
                            "Firebase Console -> Project Settings -> Service accounts -> 'Generate new private key' and place it in the firebase/ folder."
                        )

            if cred:
                firebase_admin.initialize_app(cred)
                _firebase_initialized = True
                logger.info("[Firebase] Successfully initialized Firebase Admin SDK.")
            else:
                _firebase_initialized = False
                return None
        else:
            _firebase_initialized = True
        return firebase_admin.get_app()
    except Exception as e:
        logger.warning(f"[Firebase Warning] firebase-admin is not configured or failed to initialize: {e}")
        _firebase_initialized = False
        return None


def is_firebase_configured():
    """
    Checks if Firebase Admin SDK is initialized and available for sending push notifications.
    """
    try:
        app = get_firebase_app()
        return app is not None
    except Exception:
        return False


def send_push_notification(user, title, body, data=None):
    """
    Sends FCM push notification to all active DeviceToken records belonging to the given user.
    Handles invalid/expired registration tokens by automatically deactivating them.
    """
    if not user:
        return 0

    from notifications.models import DeviceToken
    device_tokens = list(DeviceToken.objects.filter(user=user, is_active=True).values_list('token', flat=True))
    if not device_tokens:
        return 0

    try:
        import firebase_admin
        from firebase_admin import messaging

        app = get_firebase_app()
        if not app:
            logger.info(f"[FCM Mock/Log] Would send push to {user.email} (tokens={len(device_tokens)}): {title} - {body}")
            return 0

        # Stringify data dict values for FCM compatibility
        safe_data = {}
        if data and isinstance(data, dict):
            for k, v in data.items():
                safe_data[str(k)] = str(v)

        notification = messaging.Notification(
            title=title,
            body=body,
        )

        # High priority Android notification config (enables sound and heads-up banner)
        android_config = messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                sound='default',
                channel_id='box4_notifications',
                click_action='FLUTTER_NOTIFICATION_CLICK',
            )
        )

        # APNS config for iOS devices (enables badge, sound, and background delivery)
        apns_config = messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    sound='default',
                    badge=1,
                    content_available=True,
                )
            )
        )

        message = messaging.MulticastMessage(
            tokens=device_tokens,
            notification=notification,
            data=safe_data,
            android=android_config,
            apns=apns_config,
        )

        response = messaging.send_each_for_multicast(message)
        success_count = response.success_count
        logger.info(f"[FCM] Sent {success_count}/{len(device_tokens)} push notifications to {user.email}")

        # Cleanup invalid/stale tokens
        if response.failure_count > 0:
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    err_code = getattr(resp.exception, 'code', None) or str(resp.exception)
                    failed_token = device_tokens[idx]
                    logger.warning(f"[FCM Warning] Token failed for {user.email} with error '{err_code}': {failed_token[:15]}...")
                    # Deactivate stale/unregistered tokens
                    if 'UNREGISTERED' in str(err_code).upper() or 'INVALID_ARGUMENT' in str(err_code).upper():
                        DeviceToken.objects.filter(token=failed_token).update(is_active=False)

        return success_count
    except Exception as e:
        logger.error(f"[FCM Error] Failed to send push notification to {getattr(user, 'email', 'unknown')}: {e}", exc_info=True)
        return 0
