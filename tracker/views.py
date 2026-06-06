from django.shortcuts import render, redirect
from django.contrib import messages
from tracker.models import *
from django.db.models import Sum
from django.contrib.auth.models import User
from django.db.models import Q
from django.contrib.auth import authenticate, login, logout



def index(request):

    context ={'transactions' : Transaction.objects.all().order_by('-created_at','-creation_time'),
              'balance' : Transaction.objects.all().aggregate(balance = Sum('amount'))['balance'] or 0,
              'income' : Transaction.objects.filter(amount__gte = 0).aggregate(income = Sum('amount'))['income'] or 0,
              'expense' : Transaction.objects.filter(amount__lte = 0).aggregate(expense= Sum('amount'))['expense'] or 0,
            }


    return render(request, 'index.html',context)



def login_page(request):
        if request.method == 'POST':
            username = request.POST.get('username')
            password = request.POST.get('password')

            user_obj = User.objects.filter(username = username)

            if not user_obj.exists():
                messages.error(request, 'Error : Username does not exists')
                return redirect('login')
        
            user_obj = authenticate(username = username, password = password)

            if not user_obj:
                messages.error(request, 'Error : Invalid Credentials')
                return redirect('login')
        
            login(request, user_obj)
            return redirect('/')
        
        return render(request, 'login.html')


def register_page(request):

    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        #phone = request.POST.get('phone')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        user_obj = User.objects.filter(Q(email = email) | Q(username = username))

        if user_obj.exists():
            messages.error(request, 'Error : Username or Email already exists')
            return redirect('register')
        
        if password != confirm_password:
            messages.error(request, "Error: Password and Confirm Password do not match")
            return redirect('register')
        
        user_obj = User.objects.create(
            first_name = first_name,
            last_name = last_name,
            username = username,
            email = email,
            #phone = phone
        )

        user_obj.set_password(password)
        user_obj.save()
        messages.success(request, "Sucess: Account Created")
        return redirect('register')


    return render(request, 'register.html')


def wallet(request):
    return render(request, 'wallet.html')


def Transaction_page(request):
    if request.method == "POST":
        description = request.POST.get('description')
        amount = request.POST.get('amount')

        description = description.strip()
        
        if not description:
            messages.error(request, "Description cannot be blank!!")
            return redirect('/')
        
        if not amount:
            messages.error(request, "Amount is required!!")
            return redirect('/')
        

        try:
            amount = float(amount)
        except ValueError:
            messages.error(request, "Please enter a valid number!!")
            return redirect('/')
        
        Transaction.objects.create(
            description = description,
            amount = amount,
        )
        messages.success(request, "Transaction added successfully")
        return redirect('transaction')

  
    return render(request, 'transaction.html')



def deleteTransaction(request,transaction_id):
    Transaction.objects.get(transaction_id = transaction_id).delete()
    return redirect('/')

