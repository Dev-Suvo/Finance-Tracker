from django.urls import path
from .views import (
    LandingPageView,
    LoginPageView,
    RegisterPageView,
    HomePageView,
    CreateWalletPageView,
    SelectWalletPageView,
    MainMenuPageView,
    CreateTransactionPageView,
    DashboardPageView,
    LogoutPageView,
    AllTransactionsView,
    UpdateTransactionView,
    DeleteTransactionView,
    ExportCSVView,
    ExportPDFView,
    BudgetListView,
    CreateBudgetView,
    DeleteBudgetView,
    VerifyEmailView,
    SavingsGoalListView,
    CreateSavingsGoalView,
    DeleteSavingsGoalView,
    SavingsGoalDetailView,
    DepositToGoalView,
    WithdrawFromGoalView,
    DeleteGoalTransactionView,
)

urlpatterns = [
    path('', LandingPageView.as_view(), name='landing'),
    path('login/', LoginPageView.as_view(), name='login'),
    path('register/', RegisterPageView.as_view(), name='register'),
    path('verify-email/<str:token>/', VerifyEmailView.as_view(), name='verify_email'),

    path('home/', HomePageView.as_view(), name='home'),

    path('wallet/create/', CreateWalletPageView.as_view(), name='create_wallet'),
    path('wallet/select/', SelectWalletPageView.as_view(), name='select_wallet'),

    path('menu/', MainMenuPageView.as_view(), name='main_menu'),

    path('transaction/create/', CreateTransactionPageView.as_view(), name='create_transaction'),
    path('update-transaction/<uuid:transaction_id>/', UpdateTransactionView.as_view(), name='update_transaction'),
    path('delete-transaction/<uuid:transaction_id>/', DeleteTransactionView.as_view(), name='delete_transaction'),

    path('dashboard/', DashboardPageView.as_view(), name='dashboard'),

    path('logout/', LogoutPageView.as_view(), name='logout'),

    path('all-transactions/', AllTransactionsView.as_view(), name='all_transactions'),

    path('export/csv/', ExportCSVView.as_view(), name='export_csv'),
    path('export/pdf/', ExportPDFView.as_view(), name='export_pdf'),

    path('budgets/', BudgetListView.as_view(), name='budgets'),
    path('budget/create/', CreateBudgetView.as_view(), name='create_budget'),
    path('budget/delete/<uuid:budget_id>/', DeleteBudgetView.as_view(), name='delete_budget'),

    path('savings-goals/', SavingsGoalListView.as_view(), name='savings_goals'),
    path('savings-goal/create/', CreateSavingsGoalView.as_view(), name='create_savings_goal'),
    path('savings-goal/delete/<uuid:goal_id>/', DeleteSavingsGoalView.as_view(), name='delete_savings_goal'),
    path('savings-goal/<uuid:goal_id>/', SavingsGoalDetailView.as_view(), name='savings_goal_detail'),
    path('savings-goal/<uuid:goal_id>/deposit/', DepositToGoalView.as_view(), name='deposit_to_goal'),
    path('savings-goal/<uuid:goal_id>/withdraw/', WithdrawFromGoalView.as_view(), name='withdraw_from_goal'),
    path('savings-goal/transaction/<uuid:tx_id>/delete/', DeleteGoalTransactionView.as_view(), name='delete_goal_transaction'),
]
