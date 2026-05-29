from django.urls import path
from tracker.views import *

urlpatterns = [
    path('', index, name='index'),
    path('delete-transaction/<uuid>',deleteTransaction, name='deleteTransaction')
]
