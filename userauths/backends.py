from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class EmailBackend(ModelBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        """
        Allow authentication using either email or phone_number.
        Keeps compatibility with authenticate(request, email=..., password=...)
        """

        if email and password:
            try:
                user = User.objects.filter(
                    Q(email__iexact=email) | Q(phone_number__iexact=email)
                ).first()

                if user and user.check_password(password) and self.user_can_authenticate(user):
                    return user

            except User.DoesNotExist:
                pass

        return None

    def user_can_authenticate(self, user):
        return user.is_active