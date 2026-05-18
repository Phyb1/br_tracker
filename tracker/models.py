"""
BR Bale Tracker Data Models

Models for tracking tobacco bales from BR receipt through collection at TSF Mvurwi.
Implements stack collapse logic, audit trail, and performance-optimized queries.

Key Concepts:
- BRRecord: Daily bale receipt document from auction floor
- Bale: Individual bale with location and status
- BaleHistory: Immutable audit log for compliance
- Stack Collapse: When a bale is removed, levels above shift down to fill the gap
"""

from __future__ import annotations
from typing import TYPE_CHECKING, TypedDict, Dict, Any
from decimal import Decimal

from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db.models import Q, Count, Sum, F, Avg, Max, Min

if TYPE_CHECKING:
    from django.db.models import QuerySet

class Floor(models.TextChoices):
    """Warehouse floor identifiers."""
    A = 'A', _('Floor A')
    B = 'B', _('Floor B')
    C = 'C', _('Floor C')
    D = 'D', _('Floor D')

class Side(models.TextChoices):
    """Stack side for double-sided rows."""
    LEFT = 'L', _('Left')
    RIGHT = 'R', _('Right')

class BaleStatus(models.TextChoices):
    """Lifecycle status of a bale."""
    IN_STOCK = 'InStock', _('In Stock - Available for Collection')
    RESERVED = 'Reserved', _('Reserved - Awaiting Collection')
    COLLECTED = 'Collected', _('Collected by Farmer')
    REMOVED = 'Removed', _('Removed - Damaged/Discarded')

class BaleReason(models.TextChoices):
    """Condition/reason codes for quality control."""
    GOOD = 'GOOD', _('Good Condition')
    OVERWEIGHT = 'OVERWEIGHT', _('Overweight >100kg')
    UNDERWEIGHT = 'UNDERWEIGHT', _('Underweight <40kg')
    WET = 'WET', _('Wet/Damp')
    MOULDY = 'MOULDY', _('Mouldy/Musty')
    DAMAGED = 'DAMAGED', _('Physically Damaged')
    MIXED = 'MIXED', _('Mixed Grades')
    INFESTED = 'INFESTED', _('Pest Infested')
    OTHER = 'OTHER', _('Other - See Notes')

class MetricsDict(TypedDict):
    """Type for in_out_ratio return value."""
    intake: int
    outflow: int
    ratio: float
    net_change: int

class BRRecord(models.Model):
    """
    Bale Receipt record from auction floor.

    Represents a single BR document. All bales in this BR share the same
    sale_date and are recorded by one BR Clerk.

    Attributes:
        br_number: Unique BR identifier from auction floor
        sale_date: Date of auction sale
        received_date: Timestamp when bales arrived at TSF
        recorded_by: BR Clerk who entered this record
        total_bales: Expected bale count from BR document
        total_mass: Expected total mass from BR document
        notes: Freeform notes for discrepancies
    """
    br_number = models.CharField(
        _('BR Number'),
        max_length=30,
        unique=True,
        db_index=True,
        help_text=_('Unique BR number from auction floor')
    )
    sale_date = models.DateField(_('Sale Date'), db_index=True)
    received_date = models.DateTimeField(
        _('Date Received at TSF'),
        db_index=True,
        help_text=_('Timestamp when bales physically arrived')
    )
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='br_records',
        limit_choices_to={'groups__name': 'BR Clerk'},
        help_text=_('BR Clerk who recorded this BR')
    )
    total_bales = models.PositiveIntegerField(_('Total Bales on BR'))
    total_mass = models.DecimalField(
        _('Total Mass'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Total mass in kg from BR document')
    )
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sale_date', '-br_number']
        indexes = [
            models.Index(fields=['sale_date', 'received_date'], name='br_date_idx')
        ]
        verbose_name = _('BR Record')
        verbose_name_plural = _('BR Records')

    def __str__(self) -> str:
        return f"BR {self.br_number} - {self.sale_date}"

class BaleQuerySet(models.QuerySet):
    """Custom queryset for Bale with domain-specific filters."""

    def in_stock(self) -> QuerySet[Bale]:
        """Return bales available for collection."""
        return self.filter(status=BaleStatus.IN_STOCK)

    def collected(self) -> QuerySet[Bale]:
        """Return bales already collected by farmers."""
        return self.filter(status=BaleStatus.COLLECTED)

    def defects(self) -> QuerySet[Bale]:
        """Return bales with quality issues."""
        return self.exclude(reason=BaleReason.GOOD)

    def by_location(
        self,
        floor: str,
        stack: str,
        row: int,
        side: str
    ) -> QuerySet[Bale]:
        """Filter bales by exact location."""
        return self.filter(floor=floor, stack=stack, row=row, side=side)

    def daily_metrics(self, date) -> Dict[str, Any]:
        """
        Calculate intake/outflow metrics for a specific date.

        Returns:
            Dict with intake, intake_mass, collected, defects, avg_dwell
        """
        qs = self.filter(date_scanned__date=date)
        return qs.aggregate(
            intake=Count('id'),
            intake_mass=Sum('mass'),
            collected=Count('id', filter=Q(status=BaleStatus.COLLECTED)),
            defects=Count('id', filter=~Q(reason=BaleReason.GOOD)),
            avg_dwell=Avg(
                F('date_collected') - F('date_scanned'),
                filter=Q(status=BaleStatus.COLLECTED)
            )
        )

    def in_out_ratio(self, start_date, end_date) -> MetricsDict:
        """
        Calculate intake vs outflow ratio for date range.

        Args:
            start_date: Start date inclusive
            end_date: End date inclusive

        Returns:
            Dict with intake, outflow, ratio, net_change
        """
        qs = self.filter(br_record__sale_date__range=[start_date, end_date])
        intake = qs.count()
        outflow = qs.filter(
            date_collected__date__range=[start_date, end_date]
        ).count()

        return MetricsDict(
            intake=intake,
            outflow=outflow,
            ratio=round(outflow / intake, 2) if intake else 0.0,
            net_change=intake - outflow
        )

BaleManager = models.Manager.from_queryset(BaleQuerySet)

class Bale(models.Model):
    """
    Individual tobacco bale with location tracking.

    Implements stack collapse: when a bale is collected, levels above
    automatically shift down to fill the gap.

    Attributes:
        br_record: Source BR record
        barcode: Physical barcode on bale
        grower_no: Farmer/grower identifier
        location: floor, stack, row, side, level combination
        status: Current lifecycle status
        reason: Quality condition code
    """
    br_record = models.ForeignKey(
        BRRecord,
        on_delete=models.PROTECT,
        related_name='bales'
    )
    barcode = models.CharField(
        _('Barcode'),
        max_length=50,
        db_index=True,
        help_text=_('Physical barcode on bale'),
        blank=True
    )
    grower_no = models.CharField(
        _('Grower Number'),
        max_length=20,
        db_index=True
    )
    lot_no = models.CharField(_('Lot Number'), max_length=20, db_index=True)
    mass = models.DecimalField(
        _('Mass'),
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    reason = models.CharField(
        _('Condition / Reason'),
        max_length=15,
        choices=BaleReason.choices,
        default=BaleReason.GOOD,
        db_index=True
    )
    reason_notes = models.CharField(_('Reason Notes'), max_length=200, blank=True)

    # Location fields
    floor = models.CharField(
        _('Floor'),
        max_length=1,
        choices=Floor.choices,
        default=Floor.A
    )
    stack = models.CharField(_('Stack'), max_length=15)
    row = models.PositiveSmallIntegerField(
        _('Row'),
        validators=[MinValueValidator(1), MaxValueValidator(34)]
    )
    side = models.CharField(
        _('Side'),
        max_length=1,
        choices=Side.choices,
        default=Side.LEFT
    )
    level = models.PositiveSmallIntegerField(
        _('Level'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_('Vertical position in stack, 1 is bottom')
    )

    # Status and timestamps
    status = models.CharField(
        _('Status'),
        max_length=15,
        choices=BaleStatus.choices,
        default=BaleStatus.IN_STOCK,
        db_index=True
    )
    date_received = models.DateTimeField(
        _('Date Received'),
        null=True,
        blank=True,
        db_index=True
    )
    date_scanned = models.DateTimeField(
        _('Date Scanned'),
        auto_now_add=True,
        db_index=True
    )
    date_collected = models.DateTimeField(
        _('Date Collected'),
        null=True,
        blank=True,
        db_index=True
    )

    # User tracking
    scanned_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='bales_scanned',
        limit_choices_to={'groups__name': 'BR Clerk'}
    )
    collected_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='bales_collected',
        limit_choices_to={'groups__name': 'Collection Dept'}
    )

    objects = BaleManager()

    class Meta:
        ordering = ['floor', 'stack', 'row', 'side', 'level']
        indexes = [
            models.Index(
                fields=['status', 'floor', 'stack', 'row', 'side'],
                name='bale_location_idx'
            ),
            models.Index(fields=['br_record', 'date_scanned'], name='bale_br_date_idx'),
            models.Index(fields=['grower_no', 'lot_no', 'status'], name='bale_grower_idx'),
            models.Index(fields=['date_scanned'], name='bale_scanned_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['floor', 'stack', 'row', 'side', 'level', 'status'],
                condition=Q(status=BaleStatus.IN_STOCK),
                name='unique_slot_in_stock'
            ),
            models.UniqueConstraint(
                fields=['br_record', 'barcode'],
                name='unique_bale_per_br'
            )
        ]
        verbose_name = _('Bale')
        verbose_name_plural = _('Bales')

    def __str__(self) -> str:
        return f"{self.barcode} - {self.grower_no}"

    @property
    def location_display(self) -> str:
        """Human-readable location string for UI."""
        return f"FLOOR-{self.floor} {self.stack} Row {self.row} {self.get_side_display()} L{self.level}"

    @property
    def is_available(self) -> bool:
        """Check if bale is available for collection."""
        return self.status == BaleStatus.IN_STOCK

    @property
    def is_defect(self) -> bool:
        """Check if bale has quality issues."""
        return self.reason!= BaleReason.GOOD

    @transaction.atomic
    def reserve_for_collection(self, user: User) -> None:
        """
        Reserve bale for collection by farmer.

        Args:
            user: Collection Dept user performing the action

        Raises:
            ValidationError: If bale is not in stock
        """
        if self.status!= BaleStatus.IN_STOCK:
            raise ValidationError(_('Bale not available for collection'))
        self.status = BaleStatus.RESERVED
        self.save(update_fields=['status'])

    @transaction.atomic
    def mark_collected(self, user: User) -> None:
        """
        Mark bale as collected and trigger stack collapse.

        Args:
            user: Collection Dept user performing the action

        Raises:
            ValidationError: If bale is not available
        """
        if self.status not in [BaleStatus.IN_STOCK, BaleStatus.RESERVED]:
            raise ValidationError(_('Bale not available for collection'))

        self.status = BaleStatus.COLLECTED
        self.date_collected = timezone.now()
        self.collected_by = user
        self.save(update_fields=['status', 'date_collected', 'collected_by'])

        # Collapse stack levels above this position
        Bale.reorder_levels(self.floor, self.stack, self.row, self.side)

    @classmethod
    @transaction.atomic
    def reorder_levels(cls, floor: str, stack: str, row: int, side: str) -> None:
        """
        Collapse stack levels to fill gaps after bale removal.

        All bales above the removed level shift down by 1.
        Runs in a single bulk_update for performance.

        Args:
            floor: Floor identifier
            stack: Stack identifier
            row: Row number
            side: Side identifier
        """
        bales = list(
            cls.objects.in_stock()
           .filter(floor=floor, stack=stack, row=row, side=side)
           .order_by('level')
        )

        updates = []
        for idx, bale in enumerate(bales, start=1):
            if bale.level!= idx:
                bale.level = idx
                updates.append(bale)

        if updates:
            cls.objects.bulk_update(updates, ['level'])

    def clean(self) -> None:
        """
        Validate stack naming convention.

        Enforces: stack must be STACK-{floor}
        """
        if self.stack!= f'STACK-{self.floor}':
            raise ValidationError({
                'stack': _('Stack must follow format STACK-{floor}')
            })

class BaleHistory(models.Model):
    """
    Immutable audit trail for bale changes.

    Logs every status and location change. Created via signals on save.
    Records are never deleted or updated for compliance.

    Attributes:
        bale: Related bale
        old_status/new_status: Status before and after change
        old_location/new_location: Location before and after change
        changed_by: User who made the change
        changed_at: Timestamp of change
    """
    bale = models.ForeignKey(
        Bale,
        on_delete=models.CASCADE,
        related_name='history'
    )
    old_status = models.CharField(max_length=15)
    old_location = models.CharField(max_length=100, blank=True)
    new_status = models.CharField(max_length=15)
    new_location = models.CharField(max_length=100, blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.PROTECT)
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['bale', 'changed_at'], name='history_bale_time_idx')
        ]
        verbose_name = _('Bale History')
        verbose_name_plural = _('Bale History')
        get_latest_by = 'changed_at'

    def __str__(self) -> str:
        return f"{self.bale.barcode}: {self.old_status} → {self.new_status}"
