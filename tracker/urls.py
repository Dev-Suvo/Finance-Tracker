from django.urls import path
from tracker.views import *

urlpatterns = [
    path('', index, name='index'),
    path('login/', login_page, name='login'),
    path('register/', register_page, name='register'),
    path('wallet/', wallet, name='wallet'),
    path('transaction/', Transaction_page, name='transaction'),
    path('delete-transaction/<transaction_id>',deleteTransaction, name='deleteTransaction'),

]
