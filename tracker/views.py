from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from decimal import Decimal
from .models import *
from django.shortcuts import get_object_or_404
import re



def landing_page(request):

    return render(request, 'landing.html')




def login_page(request):

    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')

        user = authenticate(username=username,password=password)

        if user is None:
            messages.error(request,'Invalid Username or Password')
            return redirect('login')


        login(request, user)

        if remember_me:
            request.session.set_expiry(1209600)  # 2 weeks
        else:
            request.session.set_expiry(0)

        return redirect('home')


    return render(request, 'login.html')



def register_page(request):

    if request.method == 'POST':

        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number', '').strip()
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')


        if User.objects.filter(username=username).exists():

            messages.error(request,'Username already exists')
            return redirect('register')


        if User.objects.filter(email=email).exists():

            messages.error(request,'Email already exists')
            return redirect('register')

        if not re.fullmatch(r'\d{10}', phone_number):

            messages.error(request,'Phone number must be exactly 10 digits')
            return redirect('register')

        if UserProfile.objects.filter(phone_number=phone_number).exists():

            messages.error(request,'Phone number already registered')
            return redirect('register')

        if password != confirm_password:

            messages.error(request,'Passwords do not match')
            return redirect('register')


        user = User.objects.create_user(

            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            password=password
        )

        UserProfile.objects.create(
            user=user,
            phone_number=phone_number
        )

        messages.success(request,'Account Created Successfully')
        return redirect('login')

    return render(request, 'register.html')




@login_required
def home_page(request):

    wallets = Wallet.objects.filter(user=request.user)
    context = {'wallets': wallets}

    return render(request,'home.html',context)




@login_required
def create_wallet_page(request):

    if request.method == 'POST':

        wallet_name = request.POST.get('wallet_name').strip()

        if not wallet_name:
            messages.error(request,'Wallet name is required')

            return redirect('create_wallet')

        Wallet.objects.create(
            user=request.user,
            wallet_name=wallet_name
        )

        messages.success(request,'Wallet Created Successfully')

        return redirect('select_wallet')

    return render(request,'create_wallet.html')




@login_required
def select_wallet_page(request):

    wallets = Wallet.objects.filter(user=request.user)

    if request.method == 'POST':

        wallet_id = request.POST.get('wallet_id')
        if not Wallet.objects.filter(wallet_id=wallet_id, user=request.user).exists():
            messages.error(request, 'Invalid wallet selected')
            return redirect('select_wallet')
        request.session['wallet_id'] = str(wallet_id)
        return redirect('main_menu')

    context = {'wallets': wallets}
    return render(request,'select_wallet.html',context)





@login_required
def main_menu_page(request):

    wallet_id = request.session.get('wallet_id')
    if not wallet_id:
        return redirect('select_wallet')

    try:

        wallet = Wallet.objects.get(wallet_id=wallet_id,user=request.user)

    except Wallet.DoesNotExist:

        return redirect('select_wallet')

    context = {'wallet': wallet}
    return render(request,'main_menu.html',context)



@login_required
def create_transaction_page(request):

    wallet_id = request.session.get('wallet_id')

    if not wallet_id:
        return redirect('select_wallet')

    try:
        wallet = Wallet.objects.get(
            wallet_id=wallet_id,
            user=request.user
        )

    except Wallet.DoesNotExist:
        return redirect('select_wallet')


    if request.method == 'POST':

        transaction_type = request.POST.get('transaction_type')
        description = request.POST.get('description')
        category = request.POST.get('category')


        try:
            amount = Decimal(request.POST.get('amount'))

        except:
            messages.error(request,'Enter a valid amount')
            return redirect('create_transaction')


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

        messages.success(request,'Transaction Added Successfully')
        return redirect('dashboard')

    context = {'wallet': wallet}
    return render(request,'create_transaction.html',context)




#helperFunction



def get_category_breakdown(wallet, tx_type):
    qs = (Transaction.objects
          .filter(wallet=wallet, transaction_type=tx_type)
          .values('category')
          .annotate(total=Sum('amount'))
          .order_by('-total'))

    total_amount = sum(row['total'] for row in qs) or 0
    colors = ['#7c3aed', '#10b981', '#f59e0b', '#ef4444', '#3b82f6', '#64748b']

    breakdown = []
    cumulative = 0
    for i, row in enumerate(qs):
        amount = row['total']
        percent = round((amount / total_amount) * 100, 1) if total_amount else 0
        breakdown.append({
            'category': row['category'],
            'amount': amount,
            'percent': percent,
            'color': colors[i % len(colors)],
            'dasharray': f'{percent} {100 - percent}',
            'dashoffset': 25 - cumulative,
        })
        cumulative += percent

    return breakdown, total_amount




@login_required
def dashboard_page(request):

    wallet_id = request.session.get('wallet_id')

    if not wallet_id:
        return redirect('select_wallet')

    try:
        wallet = Wallet.objects.get(
            wallet_id=wallet_id,
            user=request.user
        )

    except Wallet.DoesNotExist:
        return redirect('select_wallet')


    transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at', '-creation_time', '-transaction_id',)[:3]
    all_transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at', '-creation_time', '-transaction_id',)

    income = Transaction.objects.filter(wallet=wallet,transaction_type='Income').aggregate(total=Sum('amount'))['total'] or 0
    expense = Transaction.objects.filter(wallet=wallet,transaction_type='Expense').aggregate(total=Sum('amount'))['total'] or 0

    expense_breakdown, _ = get_category_breakdown(wallet, 'Expense')
    income_breakdown, _ = get_category_breakdown(wallet, 'Income')

    context = {
        'wallet': wallet,
        'transactions': transactions,
        'all_transactions': all_transactions,
        'balance': wallet.balance,
        'income': income,
        'expense': expense,
        'expense_breakdown': expense_breakdown,
        'income_breakdown': income_breakdown,
        }
    return render(request,'dashboard.html',context)





@login_required
def logout_page(request):

    request.session.flush()
    logout(request)
    return redirect('landing')



@login_required
def all_transactions(request):

    wallet_id = request.session.get('wallet_id')
    if not wallet_id:
        return redirect('select_wallet')

    try:
        wallet = Wallet.objects.get(wallet_id=wallet_id, user=request.user)
    except Wallet.DoesNotExist:
        return redirect('select_wallet')

    all_transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at', '-creation_time', '-transaction_id',)

    return render(request, 'all_transactions.html', {'wallet': wallet,'all_transactions': all_transactions})



@login_required
def update_transaction(request,transaction_id):

    transaction = get_object_or_404(Transaction, transaction_id=transaction_id, wallet__user=request.user)

    if request.method == 'POST':

        new_type = request.POST.get('transaction_type')
        new_description = request.POST.get('description')
        new_category = request.POST.get('category')

        try:
            new_amount = Decimal(
                request.POST.get('amount')
            )

        except:
            messages.error(
                request,
                'Enter a valid amount'
            )
            return redirect(
                'update_transaction',
                transaction_id=transaction_id
            )

        wallet = transaction.wallet

        if transaction.transaction_type == 'Income':
            wallet.balance -= transaction.amount
        else:
            wallet.balance += transaction.amount

        # Apply NEW transaction effect
        if new_type == 'Income':
            wallet.balance += new_amount
        else:
            wallet.balance -= new_amount

        wallet.save()

        transaction.transaction_type = new_type
        transaction.description = new_description
        transaction.category = new_category
        transaction.amount = new_amount

        transaction.save()

        messages.success(request,'Transaction Updated Successfully')
        return redirect('all_transactions')

    context = {'transaction': transaction}
    return render(request,'update_transaction.html',context)



@login_required
def delete_transaction(request, transaction_id):

    transaction = get_object_or_404(Transaction, transaction_id=transaction_id, wallet__user=request.user)

    wallet = transaction.wallet
    if transaction.transaction_type == 'Income':
        wallet.balance -= transaction.amount
    else:
        wallet.balance += transaction.amount

    wallet.save()

    transaction.delete()

    messages.success(request,'Transaction Deleted Successfully')

    return redirect('all_transactions')    
