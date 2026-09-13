from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class CaseInsensitiveEmailBackend(ModelBackend):
    """
    Custom authentication backend allowing case-insensitive email authentication.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD) or kwargs.get('email')

        if username is None or password is None:
            return None

        username = str(username).strip().lower()
        try:
            user = UserModel._default_manager.get(**{f"{UserModel.USERNAME_FIELD}__iexact": username})
        except UserModel.DoesNotExist:
            # Run default password hasher once to mitigate timing attacks
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            user = UserModel._default_manager.filter(**{f"{UserModel.USERNAME_FIELD}__iexact": username}).order_by('date_joined').first()

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
