from django.db import models
from django.contrib.auth.models import User
import uuid


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Wallet(BaseModel):
    wallet_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallets')
    wallet_name = models.CharField(max_length=100)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return self.wallet_name


class Transaction(BaseModel):
    TYPE_CHOICES = (
        ('Income', 'Income'),
        ('Expense', 'Expense'),
    )

    CATEGORY_CHOICES = (
        ('Salary', 'Salary'),
        ('Freelance', 'Freelance'),
        ('Stipend', 'Stipend'),
        ('Scholarship', 'Scholarship'),
        ('Business Revenue', 'Business Revenue'),
        ('Food', 'Food'),
        ('Transport', 'Transport'),
        ('Shopping', 'Shopping'),
        ('Bills', 'Bills'),
        ('Subscription', 'Subscription'),
        ('Other', 'Other'),
    )

    transaction_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='Other')
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return self.description


class UserProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=10)
    email_verified = models.BooleanField(default=False)
    email_token = models.CharField(max_length=64, blank=True, null=True)
    welcome_email_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.phone_number}"


class Budget(BaseModel):
    CATEGORY_CHOICES = (
        ('Food', 'Food'),
        ('Transport', 'Transport'),
        ('Shopping', 'Shopping'),
        ('Bills', 'Bills'),
        ('Subscription', 'Subscription'),
        ('Other', 'Other'),
    )

    budget_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='budgets')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    limit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    period = models.CharField(max_length=10, choices=[('monthly', 'Monthly'), ('weekly', 'Weekly')], default='monthly')

    class Meta:
        unique_together = ['wallet', 'category', 'period']

    def __str__(self):
        return f"{self.wallet.wallet_name} - {self.category} ({self.period})"

    def get_spent(self):
        from django.db.models import Sum
        from django.utils import timezone
        import calendar
        now = timezone.now()

        qs = Transaction.objects.filter(
            wallet=self.wallet,
            transaction_type='Expense',
            category=self.category,
        )

        if self.period == 'monthly':
            qs = qs.filter(created_at__month=now.month, created_at__year=now.year)
        else:
            week_start = now - timezone.timedelta(days=now.weekday())
            qs = qs.filter(created_at__gte=week_start.date())

        return qs.aggregate(total=Sum('amount'))['total'] or 0

    @property
    def spent(self):
        if hasattr(self, '_cached_spent'):
            return self._cached_spent
        return self.get_spent()

    @property
    def remaining(self):
        return self.limit_amount - self.spent

    @property
    def remaining_abs(self):
        return abs(self.remaining)

    @property
    def percentage(self):
        if self.limit_amount == 0:
            return 0
        return round((self.spent / self.limit_amount) * 100, 1)


class SavingsGoal(BaseModel):
    PERIOD_CHOICES = (
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    )

    goal_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='savings_goals')
    name = models.CharField(max_length=100)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, default='monthly')
    deadline = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.target_amount}"

    @property
    def saved_amount(self):
        if hasattr(self, '_cached_saved'):
            return self._cached_saved
        from django.db.models import Sum
        deposits = self.goal_transactions.filter(transaction_type='Deposit').aggregate(
            total=Sum('amount')
        )['total'] or 0
        withdrawals = self.goal_transactions.filter(transaction_type='Withdrawal').aggregate(
            total=Sum('amount')
        )['total'] or 0
        return deposits - withdrawals

    @property
    def percentage(self):
        if self.target_amount == 0:
            return 0
        return min(round((self.saved_amount / self.target_amount) * 100, 1), 100)

    @property
    def remaining(self):
        remaining = self.target_amount - self.saved_amount
        return max(remaining, 0)


class SavingsGoalTransaction(BaseModel):
    TYPE_CHOICES = (
        ('Deposit', 'Deposit'),
        ('Withdrawal', 'Withdrawal'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    goal = models.ForeignKey(SavingsGoal, on_delete=models.CASCADE, related_name='goal_transactions')
    transaction_type = models.CharField(max_length=12, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_type}: Rs. {self.amount} for {self.goal.name}"
