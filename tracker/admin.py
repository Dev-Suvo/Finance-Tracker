from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.db.models import F
from django.db import transaction
from django.utils.html import format_html
from .models import Wallet, Transaction, UserProfile, Budget, SavingsGoal, SavingsGoalTransaction


class FinanceAdminSite(admin.AdminSite):
    site_header = 'FinanceTracker Admin'
    site_title = 'FinanceTracker'
    index_title = 'Dashboard'
    site_url = '/'
    logout_template = 'admin/logged_out.html'


admin_site = FinanceAdminSite(name='financetracker_admin')


@admin.register(User, site=admin_site)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'staff_badge', 'superuser_badge', 'active_badge', 'date_joined']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    readonly_fields = ['date_joined', 'last_login']

    def staff_badge(self, obj):
        return colored_badge('Staff', 'primary') if obj.is_staff else colored_badge('User', 'info')
    staff_badge.short_description = 'Role'

    def superuser_badge(self, obj):
        return colored_badge('Superuser', 'danger') if obj.is_superuser else '—'
    superuser_badge.short_description = 'Superuser'

    def active_badge(self, obj):
        return colored_badge('Active', 'success') if obj.is_active else colored_badge('Inactive', 'warning')
    active_badge.short_description = 'Status'


@admin.register(Group, site=admin_site)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


def colored_badge(value, color='primary'):
    colors = {
        'primary': '#7c3aed',
        'success': '#10b981',
        'danger': '#ef4444',
        'warning': '#f59e0b',
        'info': '#3b82f6',
    }
    c = colors.get(color, color)
    return format_html(
        '<span style="background:{};color:#fff;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;">{}</span>',
        c, value
    )


@admin.register(Wallet, site=admin_site)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['wallet_name', 'user', 'formatted_balance', 'created_at']
    list_filter = ['created_at']
    search_fields = ['wallet_name', 'user__username']
    readonly_fields = ['wallet_id', 'created_at', 'updated_at']

    def formatted_balance(self, obj):
        return f'Rs. {obj.balance:,.2f}'
    formatted_balance.short_description = 'Balance'
    formatted_balance.admin_order_field = 'balance'


@admin.register(Transaction, site=admin_site)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['description', 'wallet', 'colored_type', 'category', 'formatted_amount', 'created_at']
    list_filter = ['transaction_type', 'category', 'created_at']
    search_fields = ['description']
    readonly_fields = ['transaction_id', 'created_at', 'updated_at']

    def colored_type(self, obj):
        color = 'success' if obj.transaction_type == 'Income' else 'danger'
        return colored_badge(obj.transaction_type, color)
    colored_type.short_description = 'Type'

    def formatted_amount(self, obj):
        prefix = '+' if obj.transaction_type == 'Income' else '-'
        color = '#10b981' if obj.transaction_type == 'Income' else '#ef4444'
        return format_html(
            '<span style="color:{};font-weight:600;">{} Rs. {}</span>',
            color, prefix, f'{obj.amount:,.2f}'
        )
    formatted_amount.short_description = 'Amount'

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
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
        with transaction.atomic():
            wallet = obj.wallet
            if obj.transaction_type == 'Income':
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - obj.amount)
            else:
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + obj.amount)
            super().delete_model(request, obj)


@admin.register(UserProfile, site=admin_site)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'verified_badge', 'created_at']
    list_filter = ['email_verified']
    search_fields = ['user__username', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']

    def verified_badge(self, obj):
        if obj.email_verified:
            return colored_badge('Verified', 'success')
        return colored_badge('Unverified', 'warning')
    verified_badge.short_description = 'Status'


@admin.register(Budget, site=admin_site)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'category', 'formatted_limit', 'period', 'created_at']
    list_filter = ['category', 'period']
    search_fields = ['wallet__wallet_name']
    readonly_fields = ['budget_id', 'created_at', 'updated_at']

    def formatted_limit(self, obj):
        return f'Rs. {obj.limit_amount:,.2f}'
    formatted_limit.short_description = 'Limit'
    formatted_limit.admin_order_field = 'limit_amount'


@admin.register(SavingsGoal, site=admin_site)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ['name', 'wallet', 'formatted_target', 'period', 'deadline', 'active_badge', 'created_at']
    list_filter = ['period', 'is_active']
    search_fields = ['name', 'wallet__wallet_name']
    readonly_fields = ['goal_id', 'created_at', 'updated_at']

    def formatted_target(self, obj):
        return f'Rs. {obj.target_amount:,.2f}'
    formatted_target.short_description = 'Target'
    formatted_target.admin_order_field = 'target_amount'

    def active_badge(self, obj):
        if obj.is_active:
            return colored_badge('Active', 'success')
        return colored_badge('Inactive', 'danger')
    active_badge.short_description = 'Status'


@admin.register(SavingsGoalTransaction, site=admin_site)
class SavingsGoalTransactionAdmin(admin.ModelAdmin):
    list_display = ['goal', 'colored_goal_tx_type', 'formatted_amount', 'description', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['goal__name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']

    def colored_goal_tx_type(self, obj):
        color = 'success' if obj.transaction_type == 'Deposit' else 'warning'
        return colored_badge(obj.transaction_type, color)
    colored_goal_tx_type.short_description = 'Type'

    def formatted_amount(self, obj):
        prefix = '+' if obj.transaction_type == 'Deposit' else '-'
        color = '#10b981' if obj.transaction_type == 'Deposit' else '#f59e0b'
        return format_html(
            '<span style="color:{};font-weight:600;">{} Rs. {}</span>',
            color, prefix, f'{obj.amount:,.2f}'
        )
    formatted_amount.short_description = 'Amount'
