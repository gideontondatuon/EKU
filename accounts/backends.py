from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class UsernameEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or password is None:
            return None
        users = list(
            get_user_model().objects.filter(
                Q(username__iexact=username) | Q(email__iexact=username)
            )[:2]
        )
        if len(users) == 1:
            user = users[0]
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        else:
            get_user_model()().set_password(password)
        return None
