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
)

urlpatterns = [
    path('', LandingPageView.as_view(), name='landing'),
    path('login/', LoginPageView.as_view(), name='login'),
    path('register/', RegisterPageView.as_view(), name='register'),

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
]