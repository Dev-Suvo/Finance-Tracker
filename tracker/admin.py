from django.contrib import admin
from django.db.models import F
from .models import Wallet, Transaction, UserProfile, Budget, SavingsGoal, SavingsGoalTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['wallet_name', 'user', 'balance', 'created_at']
    list_filter = ['created_at']
    search_fields = ['wallet_name', 'user__username']
    readonly_fields = ['wallet_id', 'created_at', 'updated_at']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['description', 'wallet', 'transaction_type', 'category', 'amount', 'created_at']
    list_filter = ['transaction_type', 'category', 'created_at']
    search_fields = ['description']
    readonly_fields = ['transaction_id', 'created_at', 'updated_at']

    def save_model(self, request, obj, form, change):
        if change:
            old = Transaction.objects.get(pk=obj.pk)
            wallet = old.wallet
            if old.transaction_type == 'Income':
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - old.amount)
            else:
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + old.amount)
            if obj.transaction_type == 'Income':
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + obj.amount)
            else:
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - obj.amount)
        else:
            wallet = obj.wallet
            if obj.transaction_type == 'Income':
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + obj.amount)
            else:
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - obj.amount)
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        wallet = obj.wallet
        if obj.transaction_type == 'Income':
            Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - obj.amount)
        else:
            Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + obj.amount)
        super().delete_model(request, obj)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'email_verified', 'created_at']
    list_filter = ['email_verified']
    search_fields = ['user__username', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'category', 'limit_amount', 'period', 'created_at']
    list_filter = ['category', 'period']
    search_fields = ['wallet__wallet_name']
    readonly_fields = ['budget_id', 'created_at', 'updated_at']


@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ['name', 'wallet', 'target_amount', 'period', 'deadline', 'is_active', 'created_at']
    list_filter = ['period', 'is_active']
    search_fields = ['name', 'wallet__wallet_name']
    readonly_fields = ['goal_id', 'created_at', 'updated_at']


@admin.register(SavingsGoalTransaction)
class SavingsGoalTransactionAdmin(admin.ModelAdmin):
    list_display = ['goal', 'transaction_type', 'amount', 'description', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['goal__name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
