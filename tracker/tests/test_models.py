"""
Tests for BR Bale Tracker models and workflows.

Covers:
- Bale creation and validation
- Unique constraints and integrity errors
- Status transitions: reserve -> collect
- Stack collapse logic on removal
- QuerySet methods for metrics
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from django.contrib.auth.models import Group, User
from tracker.models import Bale, BRRecord, BaleHistory, Floor, Side, BaleStatus, BaleReason

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
        received_date=timezone.now(),
        recorded_by=br_clerk,
        total_bales=2,
        total_mass=200.00
    )

class TestBaleWorkflow:
    """Test core bale lifecycle and business logic."""

    def test_create_bale_via_br(self, br_record, br_clerk):
        """
        Creating a bale should set status to IN_STOCK and log history.

        Verifies:
        - Default status is IN_STOCK
        - location_display formats correctly
        - BaleHistory record is created by signal
        """
        bale = Bale.objects.create(
            br_record=br_record,
            barcode='ZLT123',
            grower_no='G001',
            lot_no='L001',
            mass=100.50,
            floor=Floor.A,
            stack='STACK-A',
            row=5,
            side=Side.LEFT,
            level=1,
            scanned_by=br_clerk
        )
        assert bale.status == BaleStatus.IN_STOCK
        assert bale.location_display == 'FLOOR-A STACK-A Row 5 Left L1'
        assert BaleHistory.objects.filter(bale=bale).exists()

    def test_unique_slot_constraint(self, br_record, br_clerk):
        """
        Only one IN_STOCK bale can occupy a physical slot.

        The unique constraint on (floor, stack, row, side, level, status)
        prevents duplicate bales in the same slot while IN_STOCK.
        """
        Bale.objects.create(
            br_record=br_record,
            barcode='B1',
            grower_no='G1',
            lot_no='L1',
            mass=100,
            floor=Floor.A,
            stack='STACK-A',
            row=1,
            side=Side.LEFT,
            level=1,
            scanned_by=br_clerk
        )
        with pytest.raises(IntegrityError):
            Bale.objects.create(
                br_record=br_record,
                barcode='B2',
                grower_no='G2',
                lot_no='L2',
                mass=100,
                floor=Floor.A,
                stack='STACK-A',
                row=1,
                side=Side.LEFT,
                level=1,
                scanned_by=br_clerk
            )

    def test_reserve_and_collect_workflow(self, br_record, br_clerk, collection_dept):
        """
        Test full collection workflow: create -> reserve -> collect.

        Ensures status transitions and user tracking work correctly.
        """
        bale = Bale.objects.create(
            br_record=br_record,
            barcode='B3',
            grower_no='G3',
            lot_no='L3',
            mass=100,
            floor=Floor.A,
            stack='STACK-A',
            row=2,
            side=Side.RIGHT,
            level=2,
            scanned_by=br_clerk
        )
        bale.reserve_for_collection(collection_dept)
        assert bale.status == BaleStatus.RESERVED

        bale.mark_collected(collection_dept)
        assert bale.status == BaleStatus.COLLECTED
        assert bale.collected_by == collection_dept
        assert bale.date_collected is not None

    def test_stack_collapse_after_removal(self, br_record, br_clerk):
        """
        When a bale is collected, bales above should shift down.

        This tests the stack collapse logic in Bale.reorder_levels().
        """
        b1 = Bale.objects.create(
            br_record=br_record, barcode='B1', grower_no='G1', lot_no='L1',
            mass=100, floor=Floor.B, stack='STACK-B', row=1, side=Side.LEFT,
            level=1, scanned_by=br_clerk
        )
        b2 = Bale.objects.create(
            br_record=br_record, barcode='B2', grower_no='G2', lot_no='L2',
            mass=100, floor=Floor.B, stack='STACK-B', row=1, side=Side.LEFT,
            level=2, scanned_by=br_clerk
        )
        b3 = Bale.objects.create(
            br_record=br_record, barcode='B3', grower_no='G3', lot_no='L3',
            mass=100, floor=Floor.B, stack='STACK-B', row=1, side=Side.LEFT,
            level=3, scanned_by=br_clerk
        )
        b1.mark_collected(br_clerk)

        b2.refresh_from_db()
        b3.refresh_from_db()
        assert b2.level == 1
        assert b3.level == 2

    def test_metrics_queries(self, br_record, br_clerk, collection_dept):
        """
        Test daily_metrics QuerySet method.

        Verifies intake, collected count, and aggregation work for a given date.
        """
        today = timezone.now().date()
        b1 = Bale.objects.create(
            br_record=br_record, barcode='M1', grower_no='G1', lot_no='L1',
            mass=50, floor=Floor.A, stack='STACK-A', row=1, side=Side.LEFT,
            level=1, scanned_by=br_clerk
        )
        Bale.objects.create(
            br_record=br_record, barcode='M2', grower_no='G2', lot_no='L2',
            mass=50, floor=Floor.A, stack='STACK-A', row=1, side=Side.LEFT,
            level=2, scanned_by=br_clerk
        )
        b1.mark_collected(collection_dept)

        metrics = Bale.objects.daily_metrics(today)
        assert metrics['intake'] == 2
        assert metrics['collected'] == 1
