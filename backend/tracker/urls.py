from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views import (
    RegisterView,
    VerifyEmailView,
    MeView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    WalletListView,
    DashboardView,
    TransactionListView,
    TransactionDetailView,
    ExportTransactionsView,
    BudgetListView,
    BudgetDeleteView,
    SavingsGoalListView,
    SavingsGoalDetailView,
    DepositToGoalView,
    WithdrawFromGoalView,
    DeleteGoalTransactionView,
    ReferenceDataView,
)

urlpatterns = [
    # Auth
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/verify-email/<str:token>/', VerifyEmailView.as_view(), name='verify_email'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('auth/password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('auth/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),

    # Reference data (no auth)
    path('reference/', ReferenceDataView.as_view(), name='reference'),

    # Wallets
    path('wallets/', WalletListView.as_view(), name='wallet_list'),
    path('wallets/<str:wallet_id>/dashboard/', DashboardView.as_view(), name='dashboard'),

    # Transactions
    path('wallets/<str:wallet_id>/transactions/', TransactionListView.as_view(), name='transaction_list'),
    path('transactions/<str:transaction_id>/', TransactionDetailView.as_view(), name='transaction_detail'),

    # Exports
    path('wallets/<str:wallet_id>/export/<str:fmt>/', ExportTransactionsView.as_view(), name='export'),

    # Budgets
    path('wallets/<str:wallet_id>/budgets/', BudgetListView.as_view(), name='budget_list'),
    path('budgets/<str:budget_id>/', BudgetDeleteView.as_view(), name='budget_delete'),

    # Savings goals
    path('wallets/<str:wallet_id>/goals/', SavingsGoalListView.as_view(), name='goal_list'),
    path('goals/<str:goal_id>/', SavingsGoalDetailView.as_view(), name='goal_detail'),
    path('goals/<str:goal_id>/deposit/', DepositToGoalView.as_view(), name='goal_deposit'),
    path('goals/<str:goal_id>/withdraw/', WithdrawFromGoalView.as_view(), name='goal_withdraw'),
    path('goal-transactions/<str:tx_id>/', DeleteGoalTransactionView.as_view(), name='goal_transaction_delete'),
]