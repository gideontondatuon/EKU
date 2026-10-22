from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    email = models.EmailField(unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="user_email_case_unique"),
            models.UniqueConstraint(Lower("username"), name="user_name_case_unique"),
        ]


class LoginAttempt(models.Model):
    key = models.CharField(max_length=64, unique=True)
    attempts = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField()
