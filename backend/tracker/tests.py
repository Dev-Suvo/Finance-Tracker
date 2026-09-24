from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Wallet, Transaction


class APITestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='TestPass1!', email='test@example.com')
        self.client.force_login(self.user)
        self.BASE = '/api'

    def patch_tx(self, txid, **kwargs):
        data = dict(kwargs)
        data.setdefault('description', 'updated')
        return self.client.patch(
            f'{self.BASE}/transactions/{txid}/', data,
            content_type='application/json', HTTP_HOST='localhost')

    def create_wallet(self, name='Main Wallet'):
        r = self.client.post(f'{self.BASE}/wallets/', {'wallet_name': name}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()['wallet_id']

    def create_tx(self, wallet_id, tx_type, amount, category, description='tx'):
        r = self.client.post(
            f'{self.BASE}/wallets/{wallet_id}/transactions/',
            {'transaction_type': tx_type, 'amount': amount, 'category': category, 'description': description},
            HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()['transaction_id']


class WalletAndTransactionTests(APITestBase):
    def test_create_income_and_expense_updates_balance(self):
        wid = self.create_wallet()
        self.create_tx(wid, 'Income', '1000', 'Salary')
        self.create_tx(wid, 'Expense', '300', 'Food')
        wallet = Wallet.objects.get(pk=wid)
        self.assertEqual(wallet.balance, Decimal('700.00'))

    def test_insufficient_balance_rejects_expense(self):
        wid = self.create_wallet()
        self.create_tx(wid, 'Income', '100', 'Salary')
        r = self.client.post(
            f'{self.BASE}/wallets/{wid}/transactions/',
            {'transaction_type': 'Expense', 'amount': '9999', 'category': 'Food', 'description': 'big'},
            HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 400)
        wallet = Wallet.objects.get(pk=wid)
        self.assertEqual(wallet.balance, Decimal('100.00'))

    def test_rejected_expense_patch_does_not_corrupt_balance(self):
        """Regression: PATCH that fails the insufficient-balance check must restore the original balance."""
        wid = self.create_wallet()
        self.create_tx(wid, 'Income', '100', 'Salary')
        txid = self.create_tx(wid, 'Expense', '30', 'Food')
        wallet = Wallet.objects.get(pk=wid)
        self.assertEqual(wallet.balance, Decimal('70.00'))

        r = self.patch_tx(txid, transaction_type='Expense', amount='9999', category='Food')
        self.assertEqual(r.status_code, 400)
        wallet = Wallet.objects.get(pk=wid)
        self.assertEqual(wallet.balance, Decimal('70.00'))

    def test_income_to_expense_patch_checks_balance(self):
        """Regression: an income tx edited into a too-large expense must reject and keep original balance."""
        wid = self.create_wallet()
        txid = self.create_tx(wid, 'Income', '50', 'Salary')
        r = self.patch_tx(txid, transaction_type='Expense', amount='9999', category='Food')
        self.assertEqual(r.status_code, 400)
        wallet = Wallet.objects.get(pk=wid)
        # rejected patch leaves the original income intact
        self.assertEqual(wallet.balance, Decimal('50.00'))
        tx = Transaction.objects.get(pk=txid)
        self.assertEqual(tx.transaction_type, 'Income')

    def test_delete_transaction_restores_balance(self):
        wid = self.create_wallet()
        self.create_tx(wid, 'Income', '500', 'Salary')
        txid = self.create_tx(wid, 'Expense', '200', 'Shopping')
        r = self.client.delete(f'{self.BASE}/transactions/{txid}/', HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        wallet = Wallet.objects.get(pk=wid)
        self.assertEqual(wallet.balance, Decimal('500.00'))


class BudgetTests(APITestBase):
    def test_duplicate_budget_returns_400_not_500(self):
        """Regression: same wallet/category/period must return a friendly 400, never IntegrityError 500."""
        wid = self.create_wallet()
        r1 = self.client.post(
            f'{self.BASE}/wallets/{wid}/budgets/',
            {'category': 'Food', 'limit_amount': '100', 'period': 'monthly'},
            HTTP_HOST='localhost')
        self.assertEqual(r1.status_code, 201, r1.content)
        r2 = self.client.post(
            f'{self.BASE}/wallets/{wid}/budgets/',
            {'category': 'Food', 'limit_amount': '200', 'period': 'monthly'},
            HTTP_HOST='localhost')
        self.assertEqual(r2.status_code, 400, r2.content)

    def test_budget_spent_calculation(self):
        wid = self.create_wallet()
        self.client.post(f'{self.BASE}/wallets/{wid}/budgets/',
                         {'category': 'Food', 'limit_amount': '500', 'period': 'monthly'},
                         HTTP_HOST='localhost')
        self.create_tx(wid, 'Income', '5000', 'Salary')
        self.create_tx(wid, 'Expense', '120', 'Food')
        r = self.client.get(f'{self.BASE}/wallets/{wid}/budgets/', HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200)
        budget = r.json()['budgets'][0]
        self.assertEqual(budget['spent'], '120.00')
        self.assertEqual(budget['remaining'], '380.00')
        self.assertEqual(budget['percentage'], 24.0)


class SavingsGoalTests(APITestBase):
    def test_deposit_withdraw_and_over_withdraw(self):
        wid = self.create_wallet()
        r = self.client.post(f'{self.BASE}/wallets/{wid}/goals/',
                             {'name': 'Vacation', 'target_amount': '10000', 'period': 'yearly'},
                             HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 201, r.content)
        goal_id = self.client.get(f'{self.BASE}/wallets/{wid}/goals/', HTTP_HOST='localhost').json()['goals'][0]['goal_id']

        self.client.post(f'{self.BASE}/goals/{goal_id}/deposit/',
                         {'amount': '1000', 'description': 'a'}, HTTP_HOST='localhost')
        self.client.post(f'{self.BASE}/goals/{goal_id}/withdraw/',
                         {'amount': '400', 'description': 'b'}, HTTP_HOST='localhost')
        g = self.client.get(f'{self.BASE}/goals/{goal_id}/', HTTP_HOST='localhost').json()['goal']
        self.assertEqual(g['saved_amount'], '600.00')

        r = self.client.post(f'{self.BASE}/goals/{goal_id}/withdraw/',
                             {'amount': '9999', 'description': 'too much'}, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 400)
        g = self.client.get(f'{self.BASE}/goals/{goal_id}/', HTTP_HOST='localhost').json()['goal']
        self.assertEqual(g['saved_amount'], '600.00')


class AuthTests(TestCase):
    def test_register_and_login(self):
        r = self.client.post('/api/auth/register/', {
            'first_name': 'A', 'last_name': 'B', 'username': 'newuser',
            'email': 'new@example.com', 'phone_number': '9876543210',
            'password': 'GuitarHero7!', 'confirm_password': 'GuitarHero7!',
        }, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 201, r.content)

        r = self.client.post('/api/auth/token/',
                             {'username': 'newuser', 'password': 'GuitarHero7!'},
                             HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('access', r.json())

    def test_weak_password_rejected(self):
        r = self.client.post('/api/auth/register/', {
            'first_name': 'A', 'last_name': 'B', 'username': 'weakuser',
            'email': 'weak@example.com', 'phone_number': '9876543210',
            'password': 'weak', 'confirm_password': 'weak',
        }, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 400)

    def test_reset_confirm_requires_match(self):
        r = self.client.post('/api/auth/password-reset/confirm/', {
            'uid': 'x', 'token': 'y',
            'new_password': 'NewPass1!', 'confirm_password': 'Different1!',
        }, HTTP_HOST='localhost')
        self.assertEqual(r.status_code, 400)
        self.assertIn('do not match', r.json()['detail'])