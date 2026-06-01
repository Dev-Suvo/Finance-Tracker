from django.shortcuts import render, redirect
from django.contrib import messages
from tracker.models import Transaction
from django.db.models import Sum



def index(request):

    if request.method == "POST":
        description = request.POST.get('description')
        amount = request.POST.get('amount')

        description = description.strip()
        
        if not description:
            messages.info(request, "Description cannot be blank!!")
            return redirect('/')
        
        if not amount:
            messages.info(request, "Amount is required!!")
            return redirect('/')
        

        try:
            amount = float(amount)
        except ValueError:
            messages.info(request, "Please enter a valid number!!")
            return redirect('/')
        
        Transaction.objects.create(
            description = description,
            amount = amount,
        )
        

        return redirect('/')
  

    context ={'transactions' : Transaction.objects.all().order_by('-uuid'),
              'balance' : Transaction.objects.all().aggregate(balance = Sum('amount'))['balance'] or 0,
              'income' : Transaction.objects.filter(amount__gte = 0).aggregate(income = Sum('amount'))['income'] or 0,
              'expense' : Transaction.objects.filter(amount__lte = 0).aggregate(expense= Sum('amount'))['expense'] or 0,
            }



    return render(request, 'index.html',context)


def deleteTransaction(request,uuid):
    Transaction.objects.get(uuid = uuid).delete()
    return redirect('/')



def login(request):
    return render(request, 'login.html')


def register(request):
    return render(request, 'register.html')