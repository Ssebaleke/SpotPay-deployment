from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from .models import Vendor
import re


class VendorRegistrationForm(forms.Form):
    # User fields
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    # Vendor fields
    company_name = forms.CharField(max_length=255)
    contact_person = forms.CharField(max_length=255)
    business_address = forms.CharField(max_length=100)
    business_phone = forms.CharField(max_length=15)
    business_email = forms.EmailField()

    # ---------- FIELD VALIDATION ----------

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise ValidationError("Username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError("Email already registered.")
        return email

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")

        phone = cleaned_data.get('business_phone')
        if phone and not re.match(r'^\+?1?\d{9,15}$', phone):
            self.add_error('business_phone', "Enter a valid phone number.")

        return cleaned_data

    # ---------- SAVE LOGIC (SAFE & ATOMIC) ----------

    def save(self):
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=self.cleaned_data['username'],
                    email=self.cleaned_data['email'],
                    password=self.cleaned_data['password'],
                    is_active=False
                )

                vendor = Vendor.objects.create(
                    user=user,
                    company_name=self.cleaned_data['company_name'],
                    contact_person=self.cleaned_data['contact_person'],
                    business_address=self.cleaned_data['business_address'],
                    business_phone=self.cleaned_data['business_phone'],
                    business_email=self.cleaned_data['business_email'],
                    status='PENDING'
                )

                return vendor

        except IntegrityError:
            # Absolute last line of defense (DB-level uniqueness)
            raise ValidationError("A user with this username already exists.")
