from django.urls import path
from tracker.views import *

urlpatterns = [
    path('', index, name='index'),
    path('delete-transaction/<uuid>',deleteTransaction, name='deleteTransaction'),
    path('login/', login, name='login'),
    path('register/', register, name='register'),


]
