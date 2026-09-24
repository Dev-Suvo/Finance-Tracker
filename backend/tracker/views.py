import csv
import re
import secrets

from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.db import models, transaction
from django.db.models import Sum, Q, OuterRef, Subquery, F
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .models import Wallet, Transaction, UserProfile, Budget, SavingsGoal, SavingsGoalTransaction
from .serializers import (
    UserRegisterSerializer,
    TransactionSerializer,
    BudgetSerializer,
    SavingsGoalSerializer,
    SavingsGoalTransactionSerializer,
)

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
            'amount': str(amount),
            'percent': percent,
            'color': colors[i % len(colors)],
            'dasharray': f'{percent} {100 - percent}',
            'dashoffset': 25 - cumulative,
        })
        cumulative += percent

    return breakdown, total_amount


def _safe_filename(name):
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)


# =========================================================================
#  AUTH
# =========================================================================

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            flat_errors = []
            for field, errs in serializer.errors.items():
                if isinstance(errs, list):
                    flat_errors.extend(errs)
                else:
                    flat_errors.append(str(errs))
            return Response({'errors': flat_errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        email_token = secrets.token_hex(32)

        from django.contrib.auth.password_validation import validate_password
        try:
            validate_password(data['password'])
        except Exception as e:
            return Response({'errors': [str(e)]}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            first_name=data['first_name'],
            last_name=data['last_name'],
            username=data['username'],
            email=data['email'],
            password=data['password']
        )
        UserProfile.objects.create(user=user, phone_number=data['phone_number'], email_token=email_token)

        try:
            verify_html = render_to_string('email_verify.html', {
                'frontend_url': settings.FRONTEND_URL,
                'token': email_token,
            })
            msg = EmailMultiAlternatives(
                'Verify Your Email', 'Verify your email.',
                f'FinanceTracker <{settings.EMAIL_HOST_USER}>', [user.email])
            msg.attach_alternative(verify_html, 'text/html')
            msg.send()
        except Exception:
            pass

        return Response({'detail': 'Account created. Check your email to verify.'},
                        status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        profile = UserProfile.objects.filter(email_token=token).first()
        if profile:
            profile.email_verified = True
            profile.email_token = None
            profile.save()
            return Response({'detail': 'Email verified! You can now log in.'})
        return Response({'detail': 'Invalid or expired verification link.'},
                        status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = UserProfile.objects.filter(user=user).first()
        return Response({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone_number': profile.phone_number if profile else None,
            'email_verified': profile.email_verified if profile else True,
        })


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    RATE_LIMIT_SECONDS = 60

    def post(self, request):
        last_reset = request.session.get('password_reset_time')
        if last_reset:
            from django.utils.dateparse import parse_datetime
            last_dt = parse_datetime(last_reset)
            if last_dt is not None:
                elapsed = (timezone.now() - last_dt).total_seconds()
                if elapsed < self.RATE_LIMIT_SECONDS:
                    return Response(
                        {'detail': 'Please wait a minute before requesting another reset link.'},
                        status=status.HTTP_429_TOO_MANY_REQUESTS)

        email = request.data.get('email', '').strip()
        users = User.objects.filter(email__iexact=email)

        if users.exists():
            for user in users:
                try:
                    uid = urlsafe_base64_encode(force_bytes(user.pk))
                    token = default_token_generator.make_token(user)
                    reset_url = f'{settings.FRONTEND_URL}/reset-password.html?uid={uid}&token={token}'

                    subject = render_to_string('password_reset_subject.txt').strip()
                    text_content = f'Use the following link to reset your password:\n{reset_url}'
                    html_content = render_to_string('password_reset_email.html', {
                        'frontend_url': settings.FRONTEND_URL,
                        'reset_url': reset_url,
                        'user': user,
                    })

                    msg = EmailMultiAlternatives(
                        subject, text_content,
                        f'FinanceTracker <{settings.EMAIL_HOST_USER}>', [email])
                    msg.attach_alternative(html_content, 'text/html')
                    msg.send()
                except Exception:
                    pass

        if last_reset:
            request.session['password_reset_time'] = timezone.now().isoformat()
        else:
            request.session['password_reset_time'] = timezone.now().isoformat()
        return Response({'detail': 'If that email is registered, a reset link has been sent.'})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        uid = request.data.get('uid', '')
        token = request.data.get('token', '')
        new_password = request.data.get('new_password', '')
        confirm_password = request.data.get('confirm_password', '')

        if new_password != confirm_password:
            return Response({'detail': 'Passwords do not match.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return Response({'detail': 'Invalid reset link.'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({'detail': 'Invalid or expired reset link.'},
                            status=status.HTTP_400_BAD_REQUEST)

        from django.contrib.auth.password_validation import validate_password
        try:
            validate_password(new_password, user)
        except Exception as e:
            return Response({'errors': [str(e)]}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({'detail': 'Password reset successful! You can now log in.'})


# =========================================================================
#  WALLETS
# =========================================================================

class WalletListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallets = Wallet.objects.filter(user=request.user).order_by('-created_at')
        return Response({
            'wallets': [
                {
                    'wallet_id': str(w.wallet_id),
                    'wallet_name': w.wallet_name,
                    'balance': str(w.balance),
                    'created_at': w.created_at.isoformat(),
                }
                for w in wallets
            ]
        })

    def post(self, request):
        wallet_name = (request.data.get('wallet_name') or '').strip()
        if not wallet_name:
            return Response({'errors': ['Wallet name is required']},
                            status=status.HTTP_400_BAD_REQUEST)
        wallet = Wallet.objects.create(user=request.user, wallet_name=wallet_name)
        return Response({
            'wallet_id': str(wallet.wallet_id),
            'wallet_name': wallet.wallet_name,
            'balance': str(wallet.balance),
        }, status=status.HTTP_201_CREATED)


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, wallet_id):
        wallet = Wallet.objects.filter(wallet_id=wallet_id, user=request.user).first()
        if not wallet:
            return Response({'detail': 'Wallet not found.'}, status=status.HTTP_404_NOT_FOUND)

        transactions = Transaction.objects.filter(wallet=wallet).select_related('wallet').order_by(
            '-created_at', '-transaction_id')[:3]

        income = Transaction.objects.filter(wallet=wallet, transaction_type='Income').aggregate(
            total=Sum('amount'))['total'] or 0
        expense = Transaction.objects.filter(wallet=wallet, transaction_type='Expense').aggregate(
            total=Sum('amount'))['total'] or 0
        balance = income - expense

        expense_breakdown, _ = get_category_breakdown(wallet, 'Expense')
        income_breakdown, _ = get_category_breakdown(wallet, 'Income')

        return Response({
            'wallet': {
                'wallet_id': str(wallet.wallet_id),
                'wallet_name': wallet.wallet_name,
                'balance': str(balance),
            },
            'income': str(income),
            'expense': str(expense),
            'transactions': [
                {
                    'transaction_id': str(t.transaction_id),
                    'description': t.description,
                    'transaction_type': t.transaction_type,
                    'category': t.category,
                    'amount': str(t.amount),
                    'created_at': t.created_at.isoformat(),
                    'updated_at': t.updated_at.isoformat(),
                }
                for t in transactions
            ],
            'expense_breakdown': expense_breakdown,
            'income_breakdown': income_breakdown,
        })


# =========================================================================
#  TRANSACTIONS
# =========================================================================

class TransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, wallet_id):
        wallet = Wallet.objects.filter(wallet_id=wallet_id, user=request.user).first()
        if not wallet:
            return Response({'detail': 'Wallet not found.'}, status=status.HTTP_404_NOT_FOUND)

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

        transactions = queryset.select_related('wallet').order_by('-created_at', '-transaction_id')

        return Response({
            'transactions': [
                {
                    'transaction_id': str(t.transaction_id),
                    'description': t.description,
                    'transaction_type': t.transaction_type,
                    'category': t.category,
                    'amount': str(t.amount),
                    'created_at': t.created_at.isoformat(),
                    'updated_at': t.updated_at.isoformat(),
                }
                for t in transactions
            ]
        })

    def post(self, request, wallet_id):
        wallet = Wallet.objects.filter(wallet_id=wallet_id, user=request.user).first()
        if not wallet:
            return Response({'detail': 'Wallet not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = TransactionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
            tx = serializer.save(wallet=wallet)

            if tx.transaction_type == 'Income':
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + tx.amount)
            else:
                if wallet.balance < tx.amount:
                    tx.delete()
                    return Response({'detail': 'Insufficient wallet balance.'},
                                    status=status.HTTP_400_BAD_REQUEST)
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - tx.amount)

        return Response({
            'transaction_id': str(tx.transaction_id),
            'detail': 'Transaction created.',
        }, status=status.HTTP_201_CREATED)


class TransactionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, request, transaction_id):
        return Transaction.objects.filter(
            transaction_id=transaction_id, wallet__user=request.user).select_related('wallet').first()

    def patch(self, request, transaction_id):
        tx_obj = self._get(request, transaction_id)
        if tx_obj is None:
            return Response({'detail': 'Transaction not found.'},
                            status=status.HTTP_404_NOT_FOUND)

        serializer = TransactionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        wallet = tx_obj.wallet

        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

            old_amount = tx_obj.amount
            if tx_obj.transaction_type == 'Income':
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - old_amount)
            else:
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + old_amount)

            if data['transaction_type'] == 'Income':
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + data['amount'])
            else:
                wallet.refresh_from_db()
                if wallet.balance < data['amount']:
                    if tx_obj.transaction_type == 'Income':
                        Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + old_amount)
                    else:
                        Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - old_amount)
                    return Response({'detail': 'Insufficient wallet balance.'},
                                    status=status.HTTP_400_BAD_REQUEST)
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - data['amount'])

            update_serializer = TransactionSerializer(tx_obj, data=request.data)
            if update_serializer.is_valid():
                update_serializer.save()

        return Response({'detail': 'Transaction updated.'})

    def delete(self, request, transaction_id):
        tx = self._get(request, transaction_id)
        if tx is None:
            return Response({'detail': 'Transaction not found.'},
                            status=status.HTTP_404_NOT_FOUND)

        wallet = tx.wallet
        with transaction.atomic():
            if tx.transaction_type == 'Income':
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') - tx.amount)
            else:
                Wallet.objects.filter(pk=wallet.pk).update(balance=F('balance') + tx.amount)
            tx.delete()
        return Response({'detail': 'Transaction deleted.'})


# =========================================================================
#  EXPORTS
# =========================================================================

class ExportTransactionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, wallet_id, fmt):
        wallet = Wallet.objects.filter(wallet_id=wallet_id, user=request.user).first()
        if not wallet:
            return Response({'detail': 'Wallet not found.'}, status=status.HTTP_404_NOT_FOUND)

        transactions = Transaction.objects.filter(wallet=wallet).order_by('-created_at')
        safe_name = _safe_filename(wallet.wallet_name)

        if fmt == 'csv':
            response = HttpResponse(content_type='text/csv')
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

        if fmt == 'pdf':
            response = HttpResponse(content_type='application/pdf')
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

        return Response({'detail': 'Format must be csv or pdf.'}, status=status.HTTP_400_BAD_REQUEST)


# =========================================================================
#  BUDGETS
# =========================================================================

class BudgetListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, wallet_id):
        wallet = Wallet.objects.filter(wallet_id=wallet_id, user=request.user).first()
        if not wallet:
            return Response({'detail': 'Wallet not found.'}, status=status.HTTP_404_NOT_FOUND)

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

        expense_categories = [
            c[0] for c in Transaction.CATEGORY_CHOICES
            if c[0] not in ('Salary', 'Freelance', 'Stipend', 'Scholarship', 'Business Revenue')
        ]

        budget_data = []
        for budget in budgets:
            spent = monthly_spent.get(budget.category, 0) if budget.period == 'monthly' else weekly_spent.get(budget.category, 0)
            budget_data.append({
                'budget_id': str(budget.budget_id),
                'category': budget.category,
                'limit_amount': str(budget.limit_amount),
                'period': budget.period,
                'spent': str(spent),
                'remaining': str(budget.limit_amount - spent),
                'percentage': round((spent / budget.limit_amount) * 100, 1) if budget.limit_amount else 0,
            })

        return Response({
            'budgets': budget_data,
            'expense_categories': expense_categories,
        })

    def post(self, request, wallet_id):
        wallet = Wallet.objects.filter(wallet_id=wallet_id, user=request.user).first()
        if not wallet:
            return Response({'detail': 'Wallet not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = BudgetSerializer(data=request.data)
        if not serializer.is_valid():
            flat_errors = []
            for field, errs in serializer.errors.items():
                if isinstance(errs, list):
                    flat_errors.extend(errs)
                else:
                    flat_errors.append(str(errs))
            return Response({'errors': flat_errors}, status=status.HTTP_400_BAD_REQUEST)

        if Budget.objects.filter(
            wallet=wallet, category=serializer.validated_data['category'],
            period=serializer.validated_data['period']
        ).exists():
            return Response({'errors': [f'A budget for "{serializer.validated_data["category"]}" ({serializer.validated_data["period"]}) already exists in this wallet.']},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer.save(wallet=wallet)
        return Response({'detail': 'Budget created.'}, status=status.HTTP_201_CREATED)


class BudgetDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, budget_id):
        budget = Budget.objects.filter(budget_id=budget_id, wallet__user=request.user).first()
        if budget:
            budget.delete()
            return Response({'detail': 'Budget deleted.'})
        return Response({'detail': 'Budget not found.'}, status=status.HTTP_404_NOT_FOUND)


# =========================================================================
#  SAVINGS GOALS
# =========================================================================

class SavingsGoalListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, wallet_id):
        wallet = Wallet.objects.filter(wallet_id=wallet_id, user=request.user).first()
        if not wallet:
            return Response({'detail': 'Wallet not found.'}, status=status.HTTP_404_NOT_FOUND)

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

        goal_data = []
        for goal in goals:
            saved = (goal._deposits or 0) - (goal._withdrawals or 0)
            goal_data.append({
                'goal_id': str(goal.goal_id),
                'name': goal.name,
                'target_amount': str(goal.target_amount),
                'period': goal.period,
                'deadline': goal.deadline.isoformat() if goal.deadline else None,
                'is_active': goal.is_active,
                'saved_amount': str(saved),
                'total_deposits': str(goal._deposits or 0),
                'total_withdrawals': str(goal._withdrawals or 0),
                'percentage': min(round((saved / goal.target_amount) * 100, 1), 100) if goal.target_amount else 0,
            })

        return Response({'goals': goal_data})

    def post(self, request, wallet_id):
        wallet = Wallet.objects.filter(wallet_id=wallet_id, user=request.user).first()
        if not wallet:
            return Response({'detail': 'Wallet not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SavingsGoalSerializer(data=request.data)
        if not serializer.is_valid():
            flat_errors = []
            for field, errs in serializer.errors.items():
                if isinstance(errs, list):
                    flat_errors.extend(errs)
                else:
                    flat_errors.append(str(errs))
            return Response({'errors': flat_errors}, status=status.HTTP_400_BAD_REQUEST)

        serializer.save(wallet=wallet)
        return Response({'detail': 'Savings goal created!'}, status=status.HTTP_201_CREATED)


class SavingsGoalDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, goal_id):
        goal = SavingsGoal.objects.filter(goal_id=goal_id, wallet__user=request.user).first()
        if not goal:
            return Response({'detail': 'Savings goal not found.'}, status=status.HTTP_404_NOT_FOUND)

        transactions = goal.goal_transactions.all()
        saved = goal.saved_amount

        return Response({
            'goal': {
                'goal_id': str(goal.goal_id),
                'name': goal.name,
                'target_amount': str(goal.target_amount),
                'period': goal.period,
                'deadline': goal.deadline.isoformat() if goal.deadline else None,
                'is_active': goal.is_active,
                'saved_amount': str(saved),
                'percentage': goal.percentage,
                'remaining': str(goal.remaining),
            },
            'wallet_id': str(goal.wallet.wallet_id),
            'transactions': [
                {
                    'id': str(t.id),
                    'transaction_type': t.transaction_type,
                    'amount': str(t.amount),
                    'description': t.description,
                    'created_at': t.created_at.isoformat(),
                }
                for t in transactions
            ],
        })

    def delete(self, request, goal_id):
        goal = SavingsGoal.objects.filter(goal_id=goal_id, wallet__user=request.user).first()
        if goal:
            goal.delete()
            return Response({'detail': 'Savings goal deleted.'})
        return Response({'detail': 'Savings goal not found.'}, status=status.HTTP_404_NOT_FOUND)


class DepositToGoalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, goal_id):
        goal = SavingsGoal.objects.filter(goal_id=goal_id, wallet__user=request.user).first()
        if not goal:
            return Response({'detail': 'Savings goal not found.'},
                            status=status.HTTP_404_NOT_FOUND)

        amount = request.data.get('amount', '').strip()
        description = request.data.get('description', '').strip()

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return Response({'detail': 'Enter a valid amount greater than 0.'},
                            status=status.HTTP_400_BAD_REQUEST)

        dec_amount = Decimal(str(amount))
        previous_saved = goal.saved_amount

        with transaction.atomic():
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
                    'frontend_url': settings.FRONTEND_URL,
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

        return Response({'detail': f'Deposited {CURRENCY} {amount} to {goal.name}.'},
                        status=status.HTTP_201_CREATED)


class WithdrawFromGoalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, goal_id):
        goal = SavingsGoal.objects.filter(goal_id=goal_id, wallet__user=request.user).first()
        if not goal:
            return Response({'detail': 'Savings goal not found.'},
                            status=status.HTTP_404_NOT_FOUND)

        amount = request.data.get('amount', '').strip()
        description = request.data.get('description', '').strip()

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return Response({'detail': 'Enter a valid amount greater than 0.'},
                            status=status.HTTP_400_BAD_REQUEST)

        dec_amount = Decimal(str(amount))
        if dec_amount > goal.saved_amount:
            return Response({'detail': 'Insufficient savings in this goal.'},
                            status=status.HTTP_400_BAD_REQUEST)

        SavingsGoalTransaction.objects.create(
            goal=goal,
            transaction_type='Withdrawal',
            amount=dec_amount,
            description=description or 'Withdrawal from goal',
        )

        return Response({'detail': f'Withdrew {CURRENCY} {amount} from {goal.name}.'},
                        status=status.HTTP_201_CREATED)


class DeleteGoalTransactionView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, tx_id):
        tx = SavingsGoalTransaction.objects.filter(id=tx_id, goal__wallet__user=request.user).first()
        if not tx:
            return Response({'detail': 'Transaction not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        goal = tx.goal
        tx.delete()
        return Response({'detail': 'Transaction deleted.', 'goal_id': str(goal.goal_id)})


# =========================================================================
#  REFERENCE DATA
# =========================================================================

class ReferenceDataView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'currency': CURRENCY,
            'transaction_types': [c[0] for c in Transaction.TYPE_CHOICES],
            'income_categories': ['Salary', 'Freelance', 'Stipend', 'Scholarship', 'Business Revenue', 'Other'],
            'expense_categories': ['Food', 'Transport', 'Shopping', 'Bills', 'Subscription', 'Other'],
            'budget_periods': [c[0] for c in Budget.PERIOD_CHOICES],
            'goal_periods': [c[0] for c in SavingsGoal.PERIOD_CHOICES],
        })