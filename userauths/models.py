from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

import uuid
from django.contrib.auth.base_user import BaseUserManager
from django.db.models.signals import post_save
from django.dispatch import receiver
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_admin', True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    COUNTRY_CURRENCY_MAP = {
        'KENYA': 'KES',
        'UGANDA': 'UGX',
    }


    username = None  # Disable username field
    phone_number = models.CharField(max_length=15, unique=True)
    country = models.CharField(max_length=15,blank=True, null=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    school_staff = models.BooleanField(default=False)
    is_student = models.BooleanField(default=False)
    is_teacher = models.BooleanField(default=False)
    is_parent = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_principal = models.BooleanField(default=False)
    is_deputy_principal = models.BooleanField(default=False)
    is_policy_maker = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'  # Use email as the username field
    REQUIRED_FIELDS = ['first_name', 'last_name', 'phone_number']  # Required fields for createsuperuser


    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email


class OTP(models.Model):
    """Model to store OTP information"""
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='otps')
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=50)  # login_verification, password_reset, etc.
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'purpose', 'is_used']),
            models.Index(fields=['otp_code', 'is_used']),
        ]
    
    def __str__(self):
        return f"OTP for {self.user.email if hasattr(self.user, 'email') else self.user} ({self.purpose})"
        
    def is_valid(self):
        """Check if the OTP is still valid"""
        return (
            not self.is_used and 
            self.expires_at > timezone.now() and
            self.attempts < 3
        )
