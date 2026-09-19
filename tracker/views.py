import csv
import secrets

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import redirect
from django.db import models, transaction
from django.db.models import Sum, Q, Subquery, OuterRef, F
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import TemplateHTMLRenderer
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .models import Wallet, Transaction, UserProfile, Budget, SavingsGoal, SavingsGoalTransaction
from .serializers import UserRegisterSerializer, TransactionSerializer, BudgetSerializer, SavingsGoalSerializer

REMEMBER_ME_EXPIRY = 1209600
CURRENCY = 'Rs.'


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


class FeaturesPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = []

    def get(self, request):
        return Response(template_name='features.html')


class PricingPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = []

    def get(self, request):
        return Response(template_name='pricing.html')


class SecurityPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = []

    def get(self, request):
        return Response(template_name='security.html')


class AboutPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = []

    def get(self, request):
        return Response(template_name='about.html')


class LoginPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = []

    def get(self, request):
        return Response(template_name='login.html')

    def post(self, request):
        username = request.POST.get('username') or request.data.get('username')
        password = request.POST.get('password') or request.data.get('password')
        remember_me = request.POST.get('remember_me') or request.data.get('remember_me')

        user = authenticate(username=username, password=password)

        if user is None:
            messages.error(request, 'Invalid Username or Password', extra_tags='app')
            return redirect('login')

        profile = UserProfile.objects.filter(user=user).first()
        if profile and not profile.email_verified:
            messages.error(request, 'Please verify your email before logging in.', extra_tags='app')
            return redirect('login')

        login(request, user)

        if remember_me:
            request.session.set_expiry(REMEMBER_ME_EXPIRY)
        else:
            request.session.set_expiry(0)

        if profile and not profile.welcome_email_sent:
            try:
                host = request.get_host()
                scheme = request.scheme
                html = render_to_string('email_welcome.html', {
                    'user': user, 'protocol': scheme, 'domain': host,
                })
                msg = EmailMultiAlternatives(
                    'Welcome to FinanceTracker!',
                    f'Welcome {user.first_name}!',
                    f'FinanceTracker <{settings.EMAIL_HOST_USER}>',
                    [user.email]
                )
                msg.attach_alternative(html, 'text/html')
                msg.send()
                profile.welcome_email_sent = True
                profile.save()
            except Exception:
                pass

        return redirect('home')


class RegisterPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = []

    def get(self, request):
        return Response(template_name='register.html')

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)

        if not serializer.is_valid():
            flat_errors = []
            for field, errs in serializer.errors.items():
                if isinstance(errs, list):
                    flat_errors.extend(errs)
                else:
                    flat_errors.append(str(errs))
            return Response({'form_errors': flat_errors, 'form_data': request.data.dict()}, template_name='register.html')

        data = serializer.validated_data
        email_token = secrets.token_hex(32)

        from django.contrib.auth.password_validation import validate_password
        try:
            validate_password(data['password'])
        except Exception as e:
            flat_errors = [str(e)]
            return Response({'form_errors': flat_errors, 'form_data': request.data.dict()}, template_name='register.html')

        user = User.objects.create_user(
            first_name=data['first_name'],
            last_name=data['last_name'],
            username=data['username'],
            email=data['email'],
            password=data['password']
        )

        UserProfile.objects.create(user=user, phone_number=data['phone_number'], email_token=email_token)

        host = request.get_host()
        scheme = request.scheme

        try:
            verify_html = render_to_string('email_verify.html', {
                'token': email_token, 'protocol': scheme, 'domain': host,
            })
            msg = EmailMultiAlternatives('Verify Your Email', 'Verify your email.', f'FinanceTracker <{settings.EMAIL_HOST_USER}>', [user.email])
            msg.attach_alternative(verify_html, 'text/html')
            msg.send()
        except Exception:
            pass

        messages.success(request, 'Account Created! Check your email to verify.', extra_tags='app')
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
            messages.error(request, 'Wallet name is required', extra_tags='app')
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
            messages.error(request, 'Invalid wallet selected', extra_tags='app')
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
            messages.error(request, 'Enter a valid amount', extra_tags='app')
            return redirect('create_transaction')

        tx = serializer.save(wallet=wallet)

        with transaction.atomic():
            if tx.transaction_type == 'Income':
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + tx.amount)
            else:
                if wallet.balance < tx.amount:
                    tx.delete()
                    messages.error(request, 'Insufficient wallet balance.', extra_tags='app')
                    return redirect('create_transaction')
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - tx.amount)

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

        transactions = Transaction.objects.filter(wallet=wallet).select_related('wallet').order_by('-created_at', '-transaction_id',)[:3]

        income = Transaction.objects.filter(wallet=wallet, transaction_type='Income').aggregate(total=Sum('amount'))['total'] or 0
        expense = Transaction.objects.filter(wallet=wallet, transaction_type='Expense').aggregate(total=Sum('amount'))['total'] or 0
        balance = income - expense

        expense_breakdown, _ = get_category_breakdown(wallet, 'Expense')
        income_breakdown, _ = get_category_breakdown(wallet, 'Income')

        context = {
            'wallet': wallet,
            'transactions': transactions,
            'balance': balance,
            'income': income,
            'expense': expense,
            'expense_breakdown': expense_breakdown,
            'income_breakdown': income_breakdown,
        }
        return Response(context, template_name='dashboard.html')


class LogoutPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
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

        all_transactions = queryset.select_related('wallet').order_by('-created_at', '-transaction_id',)

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
        tx = Transaction.objects.filter(transaction_id=transaction_id, wallet__user=request.user).first()
        if tx is None:
            return redirect('all_transactions')
        return Response({'transaction': tx}, template_name='update_transaction.html')

    def post(self, request, transaction_id):
        tx_obj = Transaction.objects.filter(transaction_id=transaction_id, wallet__user=request.user).first()
        if tx_obj is None:
            return redirect('all_transactions')

        serializer = TransactionSerializer(data=request.data)

        if not serializer.is_valid():
            messages.error(request, 'Enter a valid amount', extra_tags='app')
            return redirect('update_transaction', transaction_id=transaction_id)

        data = serializer.validated_data
        wallet = tx_obj.wallet

        with transaction.atomic():
            old_amount = tx_obj.amount
            if tx_obj.transaction_type == 'Income':
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - old_amount)
            else:
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + old_amount)

            if data['transaction_type'] == 'Income':
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + data['amount'])
            else:
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - data['amount'])

            serializer = TransactionSerializer(tx_obj, data=request.data)
            if serializer.is_valid():
                serializer.save()

        return redirect('all_transactions')


class DeleteTransactionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, transaction_id):
        tx = Transaction.objects.filter(transaction_id=transaction_id, wallet__user=request.user).first()
        if tx is None:
            return redirect('all_transactions')

        wallet = tx.wallet
        with transaction.atomic():
            if tx.transaction_type == 'Income':
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - tx.amount)
            else:
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + tx.amount)
            tx.delete()
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

        transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at',)

        response = HttpResponse(content_type='text/csv')
        import re
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', wallet.wallet_name)
        response['Content-Disposition'] = f'attachment; filename="transactions_{safe_name}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Description', 'Type', 'Category', 'Amount', 'Date', 'Time'])

        for tx in transactions:
            writer.writerow([
                tx.description,
                tx.transaction_type,
                tx.category,
                tx.amount,
                tx.created_at,
                tx.created_at.strftime('%H:%M'),
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

        transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at',)

        response = HttpResponse(content_type='application/pdf')
        import re
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', wallet.wallet_name)
        response['Content-Disposition'] = f'attachment; filename="transactions_{safe_name}.pdf"'

        p = canvas.Canvas(response, pagesize=A4)
        width, height = A4

        def draw_header(p, y):
            p.setFont('Helvetica-Bold', 16)
            p.drawString(50, y, f'FinanceTracker - {wallet.wallet_name}')
            p.setFont('Helvetica', 10)
            p.drawString(50, y - 25, f'Balance: {CURRENCY} {wallet.balance}')
            p.setFont('Helvetica-Bold', 11)
            y -= 60
            p.drawString(50, y, 'Description')
            p.drawString(250, y, 'Type')
            p.drawString(330, y, 'Category')
            p.drawString(430, y, 'Amount')
            p.drawString(510, y, 'Date')
            p.line(50, y - 5, width - 50, y - 5)
            return y - 25

        y = draw_header(p, height - 50)

        p.setFont('Helvetica', 10)

        for tx in transactions:
            if y < 50:
                p.showPage()
                y = draw_header(p, height - 50)
                p.setFont('Helvetica', 10)

            p.drawString(50, y, str(tx.description)[:30])
            p.drawString(250, y, tx.transaction_type)
            p.drawString(330, y, tx.category)
            p.drawString(430, y, f'{CURRENCY} {tx.amount}')
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

        from django.utils import timezone
        now = timezone.now()

        budgets = Budget.objects.filter(wallet=wallet)

        monthly_expenses = Transaction.objects.filter(
            wallet=wallet, transaction_type='Expense',
            created_at__month=now.month, created_at__year=now.year,
        ).values('category').annotate(total=Sum('amount'))
        monthly_spent = {item['category']: item['total'] or 0 for item in monthly_expenses}

        week_start = now - timezone.timedelta(days=now.weekday())
        weekly_expenses = Transaction.objects.filter(
            wallet=wallet, transaction_type='Expense',
            created_at__gte=week_start.date(),
        ).values('category').annotate(total=Sum('amount'))
        weekly_spent = {item['category']: item['total'] or 0 for item in weekly_expenses}

        for budget in budgets:
            if budget.period == 'monthly':
                budget._cached_spent = monthly_spent.get(budget.category, 0)
            else:
                budget._cached_spent = weekly_spent.get(budget.category, 0)
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
            flat_errors = []
            for field, errs in serializer.errors.items():
                if isinstance(errs, list):
                    flat_errors.extend(errs)
                else:
                    flat_errors.append(str(errs))
            messages.error(request, ' '.join(flat_errors), extra_tags='app')
            return redirect('budgets')

        serializer.save(wallet=wallet)
        messages.success(request, 'Budget created.', extra_tags='app')
        return redirect('budgets')


class DeleteBudgetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, budget_id):
        budget = Budget.objects.filter(budget_id=budget_id, wallet__user=request.user).first()
        if budget:
            budget.delete()
            messages.success(request, 'Budget deleted.', extra_tags='app')
        else:
            messages.error(request, 'Budget not found.', extra_tags='app')
        return redirect('budgets')


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
        from django.utils import timezone
        import datetime

        last_reset = request.session.get('password_reset_time')
        if last_reset:
            elapsed = (timezone.now() - timezone.datetime.fromisoformat(last_reset)).total_seconds()
            if elapsed < 60:
                messages.error(request, 'Please wait a minute before requesting another reset link.', extra_tags='app')
                return redirect('password_reset')

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

                    msg = EmailMultiAlternatives(subject, text_content, f'FinanceTracker <{settings.EMAIL_HOST_USER}>', [email])
                    msg.attach_alternative(html_content, 'text/html')
                    msg.send()
                except Exception:
                    pass

        request.session['password_reset_time'] = timezone.now().isoformat()
        return redirect('password_reset_done')


class VerifyEmailView(APIView):
    permission_classes = []

    def get(self, request, token):
        profile = UserProfile.objects.filter(email_token=token).first()
        if profile:
            profile.email_verified = True
            profile.email_token = None
            profile.save()
            messages.success(request, 'Email verified! You can now log in.', extra_tags='app')
        else:
            messages.error(request, 'Invalid or expired verification link.', extra_tags='app')
        return redirect('login')


class SavingsGoalListView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallet_id = request.session.get('wallet_id')
        if not wallet_id:
            return redirect('select_wallet')
        wallet = Wallet.objects.filter(wallet_id=wallet_id, user=request.user).first()
        if not wallet:
            return redirect('select_wallet')
        deposits = SavingsGoalTransaction.objects.filter(
            goal=OuterRef('pk'), transaction_type='Deposit'
        ).values('goal').annotate(total=Sum('amount')).values('total')
        withdrawals = SavingsGoalTransaction.objects.filter(
            goal=OuterRef('pk'), transaction_type='Withdrawal'
        ).values('goal').annotate(total=Sum('amount')).values('total')

        goals = SavingsGoal.objects.filter(wallet=wallet).annotate(
            _deposits=Subquery(deposits, output_field=models.DecimalField()),
            _withdrawals=Subquery(withdrawals, output_field=models.DecimalField()),
        )
        for goal in goals:
            goal._cached_saved = (goal._deposits or 0) - (goal._withdrawals or 0)

        return Response({'wallet': wallet, 'goals': goals}, template_name='savings_goals.html')


class CreateSavingsGoalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        wallet_id = request.session.get('wallet_id')
        if not wallet_id:
            return redirect('select_wallet')
        wallet = Wallet.objects.filter(wallet_id=wallet_id, user=request.user).first()
        if not wallet:
            return redirect('select_wallet')

        serializer = SavingsGoalSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(wallet=wallet)
            messages.success(request, 'Savings goal created!', extra_tags='app')
        else:
            messages.error(request, 'Invalid data. Please check your inputs.', extra_tags='app')
        return redirect('savings_goals')


class DeleteSavingsGoalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, goal_id):
        goal = SavingsGoal.objects.filter(goal_id=goal_id, wallet__user=request.user).first()
        if goal:
            goal.delete()
            messages.success(request, 'Savings goal deleted.', extra_tags='app')
        else:
            messages.error(request, 'Savings goal not found.', extra_tags='app')
        return redirect('savings_goals')


class SavingsGoalDetailView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    permission_classes = [IsAuthenticated]

    def get(self, request, goal_id):
        wallet_id = request.session.get('wallet_id')
        if not wallet_id:
            return redirect('select_wallet')
        try:
            wallet = Wallet.objects.get(wallet_id=wallet_id, user=request.user)
        except Wallet.DoesNotExist:
            return redirect('select_wallet')

        goal = SavingsGoal.objects.filter(goal_id=goal_id, wallet=wallet).first()
        if not goal:
            messages.error(request, 'Savings goal not found.', extra_tags='app')
            return redirect('savings_goals')

        transactions = goal.goal_transactions.all()
        return Response({
            'wallet': wallet,
            'goal': goal,
            'transactions': transactions,
        }, template_name='savings_goal_detail.html')


class DepositToGoalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, goal_id):
        wallet_id = request.session.get('wallet_id')
        if not wallet_id:
            return redirect('select_wallet')
        try:
            wallet = Wallet.objects.get(wallet_id=wallet_id, user=request.user)
        except Wallet.DoesNotExist:
            return redirect('select_wallet')

        goal = SavingsGoal.objects.filter(goal_id=goal_id, wallet=wallet).first()
        if not goal:
            messages.error(request, 'Savings goal not found.', extra_tags='app')
            return redirect('savings_goals')

        amount = request.POST.get('amount', '').strip()
        description = request.POST.get('description', '').strip()

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, 'Enter a valid amount greater than 0.', extra_tags='app')
            return redirect('savings_goal_detail', goal_id=goal_id)

        from decimal import Decimal
        dec_amount = Decimal(str(amount))

        previous_saved = goal.saved_amount

        SavingsGoalTransaction.objects.create(
            goal=goal,
            transaction_type='Deposit',
            amount=dec_amount,
            description=description or 'Deposit to goal',
        )

        if previous_saved < goal.target_amount and goal.saved_amount >= goal.target_amount:
            try:
                html = render_to_string('email_goal_complete.html', {
                    'user': request.user,
                    'goal': goal,
                })
                msg = EmailMultiAlternatives(
                    f'Congratulations! You reached your goal: {goal.name}',
                    f'You saved {CURRENCY} {goal.saved_amount} toward {goal.name}.',
                    f'FinanceTracker <{settings.EMAIL_HOST_USER}>',
                    [request.user.email]
                )
                msg.attach_alternative(html, 'text/html')
                msg.send()
            except Exception:
                pass

        messages.success(request, f'Deposited Rs. {amount} to {goal.name}.', extra_tags='app')
        return redirect('savings_goal_detail', goal_id=goal_id)


class WithdrawFromGoalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, goal_id):
        wallet_id = request.session.get('wallet_id')
        if not wallet_id:
            return redirect('select_wallet')
        try:
            wallet = Wallet.objects.get(wallet_id=wallet_id, user=request.user)
        except Wallet.DoesNotExist:
            return redirect('select_wallet')

        goal = SavingsGoal.objects.filter(goal_id=goal_id, wallet=wallet).first()
        if not goal:
            messages.error(request, 'Savings goal not found.', extra_tags='app')
            return redirect('savings_goals')

        amount = request.POST.get('amount', '').strip()
        description = request.POST.get('description', '').strip()

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, 'Enter a valid amount greater than 0.', extra_tags='app')
            return redirect('savings_goal_detail', goal_id=goal_id)

        from decimal import Decimal
        dec_amount = Decimal(str(amount))
        if dec_amount > goal.saved_amount:
            messages.error(request, 'Insufficient savings in this goal.', extra_tags='app')
            return redirect('savings_goal_detail', goal_id=goal_id)

        SavingsGoalTransaction.objects.create(
            goal=goal,
            transaction_type='Withdrawal',
            amount=dec_amount,
            description=description or 'Withdrawal from goal',
        )

        messages.success(request, f'Withdrew Rs. {amount} from {goal.name}.', extra_tags='app')
        return redirect('savings_goal_detail', goal_id=goal_id)


class DeleteGoalTransactionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, tx_id):
        tx = SavingsGoalTransaction.objects.filter(id=tx_id, goal__wallet__user=request.user).first()
        if not tx:
            messages.error(request, 'Transaction not found.', extra_tags='app')
            return redirect('savings_goals')

        goal = tx.goal
        tx.delete()
        messages.success(request, 'Transaction deleted.', extra_tags='app')
        return redirect('savings_goal_detail', goal_id=goal.goal_id)
