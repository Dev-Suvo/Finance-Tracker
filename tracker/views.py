from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from decimal import Decimal
from .models import *





# ==========================

# Landing Page

# ==========================



def landing_page(request):

    return render(request, 'landing.html')





# ==========================

# Login

# ==========================



def login_page(request):



    if request.method == 'POST':



        username = request.POST.get('username')

        password = request.POST.get('password')



        user = authenticate(

            username=username,

            password=password

        )



        if user is None:



            messages.error(

                request,

                'Invalid Username or Password'

            )



            return redirect('login')



        login(request, user)



        return redirect('home')



    return render(request, 'login.html')





# ==========================

# Register

# ==========================



def register_page(request):



    if request.method == 'POST':



        first_name = request.POST.get('first_name')

        last_name = request.POST.get('last_name')

        username = request.POST.get('username')

        email = request.POST.get('email')

        password = request.POST.get('password')

        confirm_password = request.POST.get('confirm_password')



        if User.objects.filter(

            username=username

        ).exists():



            messages.error(

                request,

                'Username already exists'

            )



            return redirect('register')



        if User.objects.filter(

            email=email

        ).exists():



            messages.error(

                request,

                'Email already exists'

            )



            return redirect('register')



        if password != confirm_password:



            messages.error(

                request,

                'Passwords do not match'

            )



            return redirect('register')



        User.objects.create_user(

            first_name=first_name,

            last_name=last_name,

            username=username,

            email=email,

            password=password

        )



        messages.success(

            request,

            'Account Created Successfully'

        )



        return redirect('login')



    return render(request, 'register.html')





# ==========================

# Home

# ==========================



@login_required

def home_page(request):



    wallets = Wallet.objects.filter(

        user=request.user

    )



    context = {

        'wallets': wallets

    }



    return render(

        request,

        'home.html',

        context

    )





# ==========================

# Create Wallet

# ==========================



@login_required

def create_wallet_page(request):



    if request.method == 'POST':



        wallet_name = request.POST.get(

            'wallet_name'

        ).strip()



        if not wallet_name:



            messages.error(

                request,

                'Wallet name is required'

            )



            return redirect(

                'create_wallet'

            )



        Wallet.objects.create(

            user=request.user,

            wallet_name=wallet_name

        )



        messages.success(

            request,

            'Wallet Created Successfully'

        )



        return redirect(

            'select_wallet'

        )



    return render(

        request,

        'create_wallet.html'

    )





# ==========================

# Select Wallet

# ==========================



@login_required

def select_wallet_page(request):



    wallets = Wallet.objects.filter(

        user=request.user

    )



    if request.method == 'POST':



        wallet_id = request.POST.get(

            'wallet_id'

        )



        request.session[

            'wallet_id'

        ] = str(wallet_id)



        return redirect(

            'main_menu'

        )



    context = {

        'wallets': wallets

    }



    return render(

        request,

        'select_wallet.html',

        context

    )





# ==========================

# Main Menu

# ==========================



@login_required

def main_menu_page(request):



    wallet_id = request.session.get(

        'wallet_id'

    )



    if not wallet_id:



        return redirect(

            'select_wallet'

        )



    try:



        wallet = Wallet.objects.get(

            wallet_id=wallet_id,

            user=request.user

        )



    except Wallet.DoesNotExist:



        return redirect(

            'select_wallet'

        )



    context = {

        'wallet': wallet

    }



    return render(

        request,

        'main_menu.html',

        context

    )





# ==========================

# Create Transaction

# ==========================



@login_required

def create_transaction_page(request):



    wallet_id = request.session.get(

        'wallet_id'

    )



    if not wallet_id:



        return redirect(

            'select_wallet'

        )



    try:



        wallet = Wallet.objects.get(

            wallet_id=wallet_id,

            user=request.user

        )



    except Wallet.DoesNotExist:



        return redirect(

            'select_wallet'

        )



    if request.method == 'POST':



        transaction_type = request.POST.get(

            'transaction_type'

        )



        description = request.POST.get(

            'description'

        )



        category = request.POST.get('category')



        try:



            amount = Decimal(

                request.POST.get(

                    'amount'

                )

            )



        except:



            messages.error(

                request,

                'Enter a valid amount'

            )



            return redirect(

                'create_transaction'

            )



        Transaction.objects.create(

            wallet=wallet,

            transaction_type=transaction_type,

            description=description,

            amount=amount,

            category = category

        )



        if transaction_type == 'Income':



            wallet.balance += amount



        else:



            wallet.balance -= amount



        wallet.save()



        messages.success(

            request,

            'Transaction Added Successfully'

        )



        return redirect(

            'dashboard'

        )



    context = {

        'wallet': wallet

    }



    return render(

        request,

        'create_transaction.html',

        context

    )





# ==========================

# Dashboard

# ==========================



@login_required

def dashboard_page(request):



    wallet_id = request.session.get(

        'wallet_id'

    )



    if not wallet_id:



        return redirect(

            'select_wallet'

        )



    try:



        wallet = Wallet.objects.get(

            wallet_id=wallet_id,

            user=request.user

        )



    except Wallet.DoesNotExist:



        return redirect(

            'select_wallet'

        )



    transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at')[:3]

    all_transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at')



    income = Transaction.objects.filter(

        wallet=wallet,

        transaction_type='Income'

    ).aggregate(

        total=Sum('amount')

    )['total'] or 0



    expense = Transaction.objects.filter(

        wallet=wallet,

        transaction_type='Expense'

    ).aggregate(

        total=Sum('amount')

    )['total'] or 0



    context = {

        'wallet': wallet,

        'transactions': transactions,

        'balance': wallet.balance,

        'income': income,

        'expense': expense,

    }



    return render(

        request,

        'dashboard.html',

        context

    )





# ==========================

# Logout

# ==========================



@login_required

def logout_page(request):



    request.session.flush()



    logout(request)



    return redirect(

        'landing'

    )





def all_transactions(request):

    wallet_id = request.session.get('wallet_id')

    wallet = Wallet.objects.get(wallet_id=wallet_id)

    all_transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at')

    return render(request, 'all_transactions.html', {

        'wallet': wallet,

        'all_transactions': all_transactions

    })

