from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from decimal import Decimal
import uuid
from datetime import timedelta


# =====================================================
# 1. VENDOR WALLET (PERMANENT – HOLDS MONEY)
# =====================================================

class VendorWallet(models.Model):
    vendor = models.OneToOneField(
        'accounts.Vendor',
        on_delete=models.CASCADE,
        related_name='wallet'
    )

    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )

    # Wallet security
    wallet_password = models.CharField(max_length=128, blank=True)
    is_locked = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---------- Security helpers ----------
    def set_wallet_password(self, raw_password):
        self.wallet_password = make_password(raw_password)
        self.is_locked = False
        self.save(update_fields=['wallet_password', 'is_locked'])

    def check_wallet_password(self, raw_password):
        return check_password(raw_password, self.wallet_password)

    def __str__(self):
        return f"{self.vendor.company_name} Wallet"


# =====================================================
# 2. WALLET PASSWORD SETUP / RESET TOKEN (TEMPORARY)
# =====================================================

class WalletPasswordToken(models.Model):
    wallet = models.OneToOneField(
        VendorWallet,
        on_delete=models.CASCADE,
        related_name='password_token'
    )

    token = models.UUIDField(default=uuid.uuid4, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

    def is_valid(self):
        return self.expires_at > timezone.now()

    def __str__(self):
        return f"Wallet password token for {self.wallet.vendor.company_name}"


# =====================================================
# 3. WALLET OTP (FOR SENSITIVE ACTIONS)
# =====================================================

class WalletOTP(models.Model):
    vendor = models.ForeignKey(
        'accounts.Vendor',
        on_delete=models.CASCADE,
        related_name='wallet_otps'
    )

    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()

    def __str__(self):
        return f"OTP for {self.vendor.company_name}"


# =====================================================
# 4. WALLET TRANSACTIONS (LEDGER)
# =====================================================
# NOTE:
# wallet is NULLABLE TEMPORARILY to allow migration of old data
# New records MUST always set wallet

class WalletTransaction(models.Model):
    CREDIT = 'credit'
    DEBIT = 'debit'

    TRANSACTION_TYPES = (
        (CREDIT, 'Credit'),
        (DEBIT, 'Debit'),
    )

    REASONS = (
        ('VOUCHER_SALE', 'Voucher Sale'),
        ('SUBSCRIPTION', 'Subscription Fee'),
        ('SMS_PURCHASE', 'SMS Purchase'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('ADJUSTMENT', 'Adjustment'),
    )

    wallet = models.ForeignKey(
        VendorWallet,
        on_delete=models.CASCADE,
        related_name='transactions',
        null=True,     # 🔑 REQUIRED for migration safety
        blank=True
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPES
    )

    reason = models.CharField(
        max_length=30,
        choices=REASONS
    )

    reference = models.CharField(
        max_length=100,
        unique=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.wallet:
            return (
                f"{self.wallet.vendor.company_name} | "
                f"{self.transaction_type.upper()} | "
                f"{self.amount}"
            )
        return f"LEGACY | {self.transaction_type.upper()} | {self.amount}"


# =====================================================
# 5. WITHDRAWAL REQUESTS (VENDOR → SPOTPAY)
# =====================================================
# NOTE:
# wallet is NULLABLE TEMPORARILY to allow migration of old rows

class WithdrawalRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_PAID = 'paid'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_PAID, 'Paid'),
        (STATUS_REJECTED, 'Rejected'),
    )

    wallet = models.ForeignKey(
        VendorWallet,
        on_delete=models.CASCADE,
        related_name='withdrawals',
        null=True,     # 🔑 REQUIRED for migration safety
        blank=True
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    reference = models.CharField(
        max_length=100,
        unique=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.wallet:
            return (
                f"{self.wallet.vendor.company_name} - "
                f"{self.amount} ({self.status})"
            )
        return f"LEGACY WITHDRAWAL - {self.amount} ({self.status})"
