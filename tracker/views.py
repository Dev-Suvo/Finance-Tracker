from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import redirect
from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import TemplateHTMLRenderer

from .models import Wallet, Transaction, UserProfile
from .serializers import UserRegisterSerializer, TransactionSerializer


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


class LandingPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = []

    def get(self, request):
        return Response(template_name='landing.html')


class LoginPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = []

    def get(self, request):
        return Response(template_name='login.html')

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        remember_me = request.data.get('remember_me')

        user = authenticate(username=username, password=password)

        if user is None:
            messages.error(request, 'Invalid Username or Password')
            return redirect('login')

        login(request, user)

        if remember_me:
            request.session.set_expiry(1209600)
        else:
            request.session.set_expiry(0)

        return redirect('home')


class RegisterPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = []

    def get(self, request):
        return Response(template_name='register.html')

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)

        if not serializer.is_valid():
            for error in serializer.errors.values():
                if isinstance(error, list):
                    for msg in error:
                        messages.error(request, msg if isinstance(msg, str) else str(msg))
                else:
                    messages.error(request, str(error))
            return redirect('register')

        data = serializer.validated_data

        user = User.objects.create_user(
            first_name=data['first_name'],
            last_name=data['last_name'],
            username=data['username'],
            email=data['email'],
            password=data['password']
        )

        UserProfile.objects.create(
            user=user,
            phone_number=data['phone_number']
        )

        messages.success(request, 'Account Created Successfully')
        return redirect('login')


class HomePageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallets = Wallet.objects.filter(user=request.user)
        return Response({'wallets': wallets}, template_name='home.html')


class CreateWalletPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(template_name='create_wallet.html')

    def post(self, request):
        wallet_name = (request.data.get('wallet_name') or '').strip()

        if not wallet_name:
            messages.error(request, 'Wallet name is required')
            return redirect('create_wallet')

        Wallet.objects.create(user=request.user, wallet_name=wallet_name)

        return redirect('select_wallet')


class SelectWalletPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallets = Wallet.objects.filter(user=request.user)
        return Response({'wallets': wallets}, template_name='select_wallet.html')

    def post(self, request):
        wallet_id = request.data.get('wallet_id')
        if not Wallet.objects.filter(wallet_id=wallet_id, user=request.user).exists():
            messages.error(request, 'Invalid wallet selected')
            return redirect('select_wallet')
        request.session['wallet_id'] = str(wallet_id)
        return redirect('main_menu')


class MainMenuPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = [IsAuthenticated]

    def _get_wallet(self, request):
        wallet_id = request.session.get('wallet_id')
        if not wallet_id:
            return None
        try:
            return Wallet.objects.get(wallet_id=wallet_id, user=request.user)
        except Wallet.DoesNotExist:
            return None

    def get(self, request):
        wallet = self._get_wallet(request)
        if wallet is None:
            return redirect('select_wallet')
        return Response({'wallet': wallet}, template_name='main_menu.html')


class CreateTransactionPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = [IsAuthenticated]

    def _get_wallet(self, request):
        wallet_id = request.session.get('wallet_id')
        if not wallet_id:
            return None
        try:
            return Wallet.objects.get(wallet_id=wallet_id, user=request.user)
        except Wallet.DoesNotExist:
            return None

    def get(self, request):
        wallet = self._get_wallet(request)
        if wallet is None:
            return redirect('select_wallet')
        return Response({'wallet': wallet}, template_name='create_transaction.html')

    def post(self, request):
        wallet = self._get_wallet(request)
        if wallet is None:
            return redirect('select_wallet')

        serializer = TransactionSerializer(data=request.data)

        if not serializer.is_valid():
            messages.error(request, 'Enter a valid amount')
            return redirect('create_transaction')

        data = serializer.validated_data
        transaction = serializer.save(wallet=wallet)

        if transaction.transaction_type == 'Income':
            wallet.balance += transaction.amount
        else:
            wallet.balance -= transaction.amount
        wallet.save()

        return redirect('dashboard')


class DashboardPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = [IsAuthenticated]

    def _get_wallet(self, request):
        wallet_id = request.session.get('wallet_id')
        if not wallet_id:
            return None
        try:
            return Wallet.objects.get(wallet_id=wallet_id, user=request.user)
        except Wallet.DoesNotExist:
            return None

    def get(self, request):
        wallet = self._get_wallet(request)
        if wallet is None:
            return redirect('select_wallet')

        transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at', '-creation_time', '-transaction_id',)[:3]
        all_transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at', '-creation_time', '-transaction_id',)

        income = Transaction.objects.filter(wallet=wallet, transaction_type='Income').aggregate(total=Sum('amount'))['total'] or 0
        expense = Transaction.objects.filter(wallet=wallet, transaction_type='Expense').aggregate(total=Sum('amount'))['total'] or 0

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
        return Response(context, template_name='dashboard.html')


class LogoutPageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        request.session.flush()
        logout(request)
        return redirect('landing')


class AllTransactionsView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = [IsAuthenticated]

    def _get_wallet(self, request):
        wallet_id = request.session.get('wallet_id')
        if not wallet_id:
            return None
        try:
            return Wallet.objects.get(wallet_id=wallet_id, user=request.user)
        except Wallet.DoesNotExist:
            return None

    def get(self, request):
        wallet = self._get_wallet(request)
        if wallet is None:
            return redirect('select_wallet')

        all_transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at', '-creation_time', '-transaction_id',)
        return Response(
            {'wallet': wallet, 'all_transactions': all_transactions},
            template_name='all_transactions.html'
        )


class UpdateTransactionView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = [IsAuthenticated]

    def get(self, request, transaction_id):
        transaction = Transaction.objects.filter(transaction_id=transaction_id, wallet__user=request.user).first()
        if transaction is None:
            return redirect('all_transactions')
        return Response({'transaction': transaction}, template_name='update_transaction.html')

    def post(self, request, transaction_id):
        transaction = Transaction.objects.filter(transaction_id=transaction_id, wallet__user=request.user).first()
        if transaction is None:
            return redirect('all_transactions')

        serializer = TransactionSerializer(data=request.data)

        if not serializer.is_valid():
            messages.error(request, 'Enter a valid amount')
            return redirect('update_transaction', transaction_id=transaction_id)

        data = serializer.validated_data
        wallet = transaction.wallet

        if transaction.transaction_type == 'Income':
            wallet.balance -= transaction.amount
        else:
            wallet.balance += transaction.amount

        if data['transaction_type'] == 'Income':
            wallet.balance += data['amount']
        else:
            wallet.balance -= data['amount']

        wallet.save()

        transaction.transaction_type = data['transaction_type']
        transaction.description = data['description']
        transaction.category = data['category']
        transaction.amount = data['amount']
        transaction.save()

        return redirect('all_transactions')


class DeleteTransactionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, transaction_id):
        transaction = Transaction.objects.filter(transaction_id=transaction_id, wallet__user=request.user).first()
        if transaction is None:
            return redirect('all_transactions')

        wallet = transaction.wallet
        if transaction.transaction_type == 'Income':
            wallet.balance -= transaction.amount
        else:
            wallet.balance += transaction.amount

        wallet.save()
        transaction.delete()

        messages.success(request, 'Transaction Deleted Successfully')
        return redirect('all_transactions')
