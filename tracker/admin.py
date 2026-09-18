from django.contrib import admin
from .models import Wallet, Transaction, UserProfile, Budget, SavingsGoal, SavingsGoalTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['wallet_name', 'user', 'balance', 'created_at']
    list_filter = ['created_at']
    search_fields = ['wallet_name', 'user__username']
    readonly_fields = ['wallet_id', 'created_at', 'creation_time', 'updated_at', 'updation_time']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['description', 'wallet', 'transaction_type', 'category', 'amount', 'created_at']
    list_filter = ['transaction_type', 'category', 'created_at']
    search_fields = ['description']
    readonly_fields = ['transaction_id', 'created_at', 'creation_time', 'updated_at', 'updation_time']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'email_verified', 'created_at']
    list_filter = ['email_verified']
    search_fields = ['user__username', 'phone_number']
    readonly_fields = ['created_at', 'creation_time', 'updated_at', 'updation_time']


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'category', 'limit_amount', 'period', 'created_at']
    list_filter = ['category', 'period']
    search_fields = ['wallet__wallet_name']
    readonly_fields = ['budget_id', 'created_at', 'creation_time', 'updated_at', 'updation_time']


@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ['name', 'wallet', 'target_amount', 'period', 'deadline', 'is_active', 'created_at']
    list_filter = ['period', 'is_active']
    search_fields = ['name', 'wallet__wallet_name']
    readonly_fields = ['goal_id', 'created_at', 'creation_time', 'updated_at', 'updation_time']


@admin.register(SavingsGoalTransaction)
class SavingsGoalTransactionAdmin(admin.ModelAdmin):
    list_display = ['goal', 'transaction_type', 'amount', 'description', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['goal__name', 'description']
    readonly_fields = ['id', 'created_at', 'creation_time', 'updated_at', 'updation_time']
