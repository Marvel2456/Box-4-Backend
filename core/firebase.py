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

            if cred:
                firebase_admin.initialize_app(cred)
                _firebase_initialized = True
                logger.info("[Firebase] Successfully initialized Firebase Admin SDK.")
            else:
                _firebase_initialized = False
        else:
            _firebase_initialized = True
        return firebase_admin.get_app()
    except Exception as e:
        logger.warning(f"[Firebase Warning] firebase-admin is not configured or failed to initialize: {e}")
        _firebase_initialized = False
        return None


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

        message = messaging.MulticastMessage(
            tokens=device_tokens,
            notification=notification,
            data=safe_data,
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
