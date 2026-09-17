from rest_framework import serializers
from django.contrib.auth.models import User
import re
from .models import UserProfile, Wallet, Transaction, Budget, SavingsGoal


class UserRegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=10)
    password = serializers.CharField()
    confirm_password = serializers.CharField()

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already exists')
        return value

    def validate_phone_number(self, value):
        value = value.strip()
        if not re.fullmatch(r'\d{10}', value):
            raise serializers.ValidationError('Phone number must be exactly 10 digits')
        if UserProfile.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError('Phone number already registered')
        return value

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError('Passwords do not match')
        return attrs


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            'transaction_id', 'wallet', 'transaction_type', 'category',
            'description', 'amount', 'created_at', 'creation_time',
            'updated_at', 'updation_time',
        ]
        read_only_fields = [
            'transaction_id', 'wallet', 'created_at', 'creation_time',
            'updated_at', 'updation_time',
        ]

    def validate_amount(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('Enter a valid amount')
        return value

    def validate_transaction_type(self, value):
        valid_types = [choice[0] for choice in Transaction.TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError('Invalid transaction type')
        return value

    def validate_category(self, value):
        valid_categories = [choice[0] for choice in Transaction.CATEGORY_CHOICES]
        if value not in valid_categories:
            raise serializers.ValidationError('Invalid category')
        return value


class BudgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Budget
        fields = ['budget_id', 'wallet', 'category', 'limit_amount', 'period']
        read_only_fields = ['budget_id', 'wallet']

    def validate_limit_amount(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('Budget limit must be greater than 0')
        return value


class SavingsGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingsGoal
        fields = ['goal_id', 'wallet', 'name', 'target_amount', 'period', 'deadline', 'is_active']
        read_only_fields = ['goal_id', 'wallet']

    def validate_target_amount(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('Target amount must be greater than 0')
        return value
