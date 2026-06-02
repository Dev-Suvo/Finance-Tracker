from django.urls import path
from tracker.views import *

urlpatterns = [
    path('', index, name='index'),
    path('login/', login, name='login'),
    path('register/', register, name='register'),
    path('wallet/', wallet, name='wallet'),
    path('transaction/', Transaction_page, name='transacion'),
    path('delete-transaction/<uuid>',deleteTransaction, name='deleteTransaction'),

]
