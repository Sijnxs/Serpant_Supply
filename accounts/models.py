from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Email2FACode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return (timezone.now() - self.created_at).total_seconds() > 300  # 5 minutes

    def __str__(self):
        return f"{self.user.username} - {self.code}"

    class Meta:
        ordering = ['-created_at']
