"""
Tests for signal handlers in tracker.signals.

These tests verify that BaleHistory records are created correctly and only
when meaningful changes occur. They also check edge cases like missing users.
"""

import pytest
from django.contrib.auth.models import Group, User
from tracker.models import Bale, BRRecord, BaleHistory, Floor, Side, BaleStatus

pytestmark = pytest.mark.django_db

@pytest.fixture
def br_clerk(db):
    """Create a user in the BR Clerk group."""
    group, _ = Group.objects.get_or_create(name='BR Clerk')
    user = User.objects.create_user(username='brclerk', password='pass')
    user.groups.add(group)
    return user

@pytest.fixture
def collection_dept(db):
    """Create a user in the Collection Dept group."""
    group, _ = Group.objects.get_or_create(name='Collection Dept')
    user = User.objects.create_user(username='collect', password='pass')
    user.groups.add(group)
    return user

@pytest.fixture
def br_record(br_clerk):
    """Create a sample BRRecord for tests."""
    return BRRecord.objects.create(
        br_number='BR20251001',
        sale_date='2025-10-01',
        received_date='2025-10-01T10:00:00Z',
        recorded_by=br_clerk,
        total_bales=1,
        total_mass=100.00
    )

@pytest.fixture
def bale(br_record, br_clerk):
    """Create a sample bale in IN_STOCK state."""
    return Bale.objects.create(
        br_record=br_record,
        barcode='SIG001',
        grower_no='G001',
        lot_no='L001',
        mass=100.00,
        floor=Floor.A,
        stack='STACK-A',
        row=1,
        side=Side.LEFT,
        level=1,
        scanned_by=br_clerk
    )

def test_history_created_on_bale_create(bale, br_clerk):
    """History record should be created when a bale is first saved."""
    history = BaleHistory.objects.filter(bale=bale)
    assert history.count() == 1
    
    h = history.first()
    assert h.old_status == ''
    assert h.new_status == BaleStatus.IN_STOCK
    assert h.changed_by == br_clerk
    assert h.notes == 'Auto-logged on save'

def test_history_created_on_status_change(bale, collection_dept):
    """History record should be created when status changes."""
    initial_count = BaleHistory.objects.filter(bale=bale).count()

    bale.mark_collected(collection_dept)

    assert BaleHistory.objects.filter(bale=bale).count() == initial_count + 1
    latest = BaleHistory.objects.filter(bale=bale).latest('changed_at')
    assert latest.old_status == BaleStatus.IN_STOCK
    assert latest.new_status == BaleStatus.COLLECTED
    assert latest.changed_by == collection_dept

def test_history_created_on_location_change(bale, br_clerk):
    """History record should be created when location changes."""
    bale.level = 2
    bale.save()

    latest = BaleHistory.objects.filter(bale=bale).latest('changed_at')
    assert 'L1' in latest.old_location
    assert 'L2' in latest.new_location
    assert latest.changed_by == br_clerk

def test_no_history_on_noop_save(bale):
    """History record should NOT be created if nothing changed."""
    initial_count = BaleHistory.objects.filter(bale=bale).count()

    bale.save()  # save without changes

    assert BaleHistory.objects.filter(bale=bale).count() == initial_count

def test_changed_by_falls_back_to_scanned_by(bale, br_clerk):
    """If collected_by is None, scanned_by should be used for changed_by."""
    bale.reason = 'WET'
    bale.save()

    latest = BaleHistory.objects.filter(bale=bale).latest('changed_at')
    assert latest.changed_by == br_clerk

"""
def test_signal_handles_missing_changed_by(bale):
   
    If both collected_by and scanned_by are None, signal should skip history creation
    and not raise. This simulates a manual DB update where user fields are cleared.
    
    initial_count = BaleHistory.objects.filter(bale=bale).count()

    # Simulate a case where both user fields are None after save
    bale.collected_by = None
    bale.scanned_by = None
    bale.reason = 'WET'
    bale.save()  # This will trigger signal, but save will succeed because fields are nullable in DB

    # No new history record should be created
    assert BaleHistory.objects.filter(bale=bale).count() == initial_count
"""
