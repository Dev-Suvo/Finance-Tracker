from django.urls import path
from .views import *

urlpatterns = [

    # Public Pages
    path('', landing_page, name='landing'),
    path('login/', login_page, name='login'),
    path('register/', register_page, name='register'),

    # Home
    path('home/', home_page, name='home'),

    # Wallet
    path('wallet/create/', create_wallet_page, name='create_wallet'),
    path('wallet/select/', select_wallet_page, name='select_wallet'),

    # Main Menu
    path('menu/', main_menu_page, name='main_menu'),

    # Transaction
    path(
        'transaction/create/',
        create_transaction_page,
        name='create_transaction'
    ),

    # Dashboard
    path('dashboard/', dashboard_page, name='dashboard'),

    # Logout
    path('logout/', logout_page, name='logout'),
]