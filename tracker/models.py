from django.db import models
from django.contrib.auth.models import User
import uuid

class BaseModel(models.Model):

    created_at = models.DateField(auto_now_add=True)
    creation_time = models.TimeField(auto_now_add=True)

    updated_at = models.DateField(auto_now=True)
    updation_time = models.TimeField(auto_now=True)

    class Meta:
        abstract = True


class Wallet(BaseModel):

    wallet_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='wallets'
    )

    wallet_name = models.CharField(max_length=100)

    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    def __str__(self):
        return self.wallet_name


class Transaction(BaseModel):

    TYPE_CHOICES = (
        ('Income', 'Income'),
        ('Expense', 'Expense'),
    )

    transaction_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transactions'
    )

    transaction_type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES
    )

    description = models.CharField(max_length=200)

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    def __str__(self):
        return self.description
