import pytest
from django.contrib.auth.models import User

@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(username='br_staff', password='test123')

@pytest.fixture
def admin_user(db):
    """Create a test superuser."""
    return User.objects.create_superuser(username='admin', password='admin123')
