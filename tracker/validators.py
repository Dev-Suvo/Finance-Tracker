import re
from django.core.exceptions import ValidationError


class ComplexityValidator:
    def validate(self, password, user=None):
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter.')
        if not re.search(r'\d', password):
            raise ValidationError('Password must contain at least one number.')
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?`~]', password):
            raise ValidationError('Password must contain at least one special character.')

    def get_help_text(self):
        return 'Your password must contain at least one uppercase letter, one number, and one special character.'
