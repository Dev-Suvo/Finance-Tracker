from django.urls import path
from .views import *

urlpatterns = [
    path('', landing_page, name='landing'),
    path('login/', login_page, name='login'),
    path('register/', register_page, name='register'),

    path('home/', home_page, name='home'),

    path('wallet/create/', create_wallet_page, name='create_wallet'),
    path('wallet/select/', select_wallet_page, name='select_wallet'),

    path('menu/', main_menu_page, name='main_menu'),

    path('transaction/create/',create_transaction_page,name='create_transaction'),
    path('update-transaction/<uuid:transaction_id>/',update_transaction,name='update_transaction'),
    path('delete-transaction/<uuid:transaction_id>/',delete_transaction,name='delete_transaction'),

    path('dashboard/', dashboard_page, name='dashboard'),

    path('logout/', logout_page, name='logout'),

    path('all-transactions/', all_transactions, name='all_transactions'),
]

