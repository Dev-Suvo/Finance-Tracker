import csv
import io

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetView
from django.contrib import messages
from django.shortcuts import redirect
from django.db.models import Sum, Q
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import TemplateHTMLRenderer
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .models import Wallet, Transaction, UserProfile, Budget
from .serializers import UserRegisterSerializer, TransactionSerializer, BudgetSerializer


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

        UserProfile.objects.create(user=user, phone_number=data['phone_number'])

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

        income = Transaction.objects.filter(wallet=wallet, transaction_type='Income').aggregate(total=Sum('amount'))['total'] or 0
        expense = Transaction.objects.filter(wallet=wallet, transaction_type='Expense').aggregate(total=Sum('amount'))['total'] or 0

        expense_breakdown, _ = get_category_breakdown(wallet, 'Expense')
        income_breakdown, _ = get_category_breakdown(wallet, 'Income')

        context = {
            'wallet': wallet,
            'transactions': transactions,
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

        queryset = Transaction.objects.filter(wallet=wallet)

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(description__icontains=search) | Q(category__icontains=search)
            )

        tx_type = request.query_params.get('type', '').strip()
        if tx_type in ('Income', 'Expense'):
            queryset = queryset.filter(transaction_type=tx_type)

        category = request.query_params.get('category', '').strip()
        if category:
            queryset = queryset.filter(category=category)

        date_from = request.query_params.get('date_from', '').strip()
        if date_from:
            try:
                queryset = queryset.filter(created_at__gte=date_from)
            except (ValueError, TypeError):
                pass

        date_to = request.query_params.get('date_to', '').strip()
        if date_to:
            try:
                queryset = queryset.filter(created_at__lte=date_to)
            except (ValueError, TypeError):
                pass

        all_transactions = queryset.order_by('-created_at', '-creation_time', '-transaction_id',)

        categories = [c[0] for c in Transaction.CATEGORY_CHOICES]

        context = {
            'wallet': wallet,
            'all_transactions': all_transactions,
            'categories': categories,
            'search': search,
            'filter_type': tx_type,
            'filter_category': category,
            'date_from': date_from,
            'date_to': date_to,
        }
        return Response(context, template_name='all_transactions.html')


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

    def post(self, request, transaction_id):
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
        return redirect('all_transactions')


class ExportCSVView(APIView):
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

        transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at', '-creation_time',)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="transactions_{wallet.wallet_name}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Description', 'Type', 'Category', 'Amount', 'Date', 'Time'])

        for tx in transactions:
            writer.writerow([
                tx.description,
                tx.transaction_type,
                tx.category,
                tx.amount,
                tx.created_at,
                tx.creation_time,
            ])

        return response


class ExportPDFView(APIView):
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

        transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at', '-creation_time',)

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="transactions_{wallet.wallet_name}.pdf"'

        p = canvas.Canvas(response, pagesize=A4)
        width, height = A4

        p.setFont('Helvetica-Bold', 16)
        p.drawString(50, height - 50, f'FinanceTracker - {wallet.wallet_name}')

        p.setFont('Helvetica', 10)
        p.drawString(50, height - 75, f'Balance: Rs. {wallet.balance}')

        p.setFont('Helvetica-Bold', 11)
        y = height - 110
        p.drawString(50, y, 'Description')
        p.drawString(250, y, 'Type')
        p.drawString(330, y, 'Category')
        p.drawString(430, y, 'Amount')
        p.drawString(510, y, 'Date')

        p.line(50, y - 5, width - 50, y - 5)

        p.setFont('Helvetica', 10)
        y -= 25

        for tx in transactions:
            if y < 50:
                p.showPage()
                y = height - 50

            p.drawString(50, y, str(tx.description)[:30])
            p.drawString(250, y, tx.transaction_type)
            p.drawString(330, y, tx.category)
            p.drawString(430, y, f'Rs. {tx.amount}')
            p.drawString(510, y, str(tx.created_at))
            y -= 20

        p.save()
        return response


class BudgetListView(APIView):
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

        budgets = Budget.objects.filter(wallet=wallet)
        expense_categories = [c[0] for c in Transaction.CATEGORY_CHOICES if c[0] not in ('Salary', 'Freelance', 'Stipend', 'Scholarship', 'Business Revenue')]

        context = {
            'wallet': wallet,
            'budgets': budgets,
            'expense_categories': expense_categories,
        }
        return Response(context, template_name='budgets.html')


class CreateBudgetView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_wallet(self, request):
        wallet_id = request.session.get('wallet_id')
        if not wallet_id:
            return None
        try:
            return Wallet.objects.get(wallet_id=wallet_id, user=request.user)
        except Wallet.DoesNotExist:
            return None

    def post(self, request):
        wallet = self._get_wallet(request)
        if wallet is None:
            return redirect('select_wallet')

        serializer = BudgetSerializer(data=request.data)

        if not serializer.is_valid():
            for error in serializer.errors.values():
                if isinstance(error, list):
                    for msg in error:
                        messages.error(request, msg if isinstance(msg, str) else str(msg))
                else:
                    messages.error(request, str(error))
            return redirect('budgets')

        serializer.save(wallet=wallet)
        return redirect('budgets')


class DeleteBudgetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, budget_id):
        budget = Budget.objects.filter(budget_id=budget_id, wallet__user=request.user).first()
        if budget:
            budget.delete()
        return redirect('budgets')


from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.views import View


class CustomPasswordResetView(View):
    def get(self, request):
        from django.shortcuts import render
        return render(request, 'password_reset.html')

    def post(self, request):
        from django.shortcuts import redirect
        from django.contrib import messages
        email = request.POST.get('email', '').strip()
        users = User.objects.filter(email__iexact=email)

        if users.exists():
            for user in users:
                try:
                    uid = urlsafe_base64_encode(force_bytes(user.pk))
                    token = default_token_generator.make_token(user)
                    host = request.get_host()
                    reset_url = f'{request.scheme}://{host}/password-reset-confirm/{uid}/{token}/'

                    subject = render_to_string('password_reset_subject.txt').strip()
                    text_content = f'Use the following link to reset your password:\n{reset_url}'
                    html_content = render_to_string('password_reset_email.html', {
                        'protocol': request.scheme,
                        'domain': host,
                        'uid': uid,
                        'token': token,
                        'user': user,
                    })

                    msg = EmailMultiAlternatives(subject, text_content, 'FinanceTracker <noreply@financetracker.com>', [email])
                    msg.attach_alternative(html_content, 'text/html')
                    sent = msg.send()
                    print(f'[PASSWORD RESET] Email sent to {email}, result={sent}')
                except Exception as e:
                    print(f'[PASSWORD RESET ERROR] {type(e).__name__}: {e}')
        else:
            print(f'[PASSWORD RESET] No user found with email: {email}')

        return redirect('password_reset_done')
