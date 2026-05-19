"""
BR Bale Tracker Data Models
"""
from __future__ import annotations
from typing import TYPE_CHECKING, TypedDict, Dict, Any
from decimal import Decimal

from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db.models import Q, Count, Sum, F, Avg

if TYPE_CHECKING:
    from django.db.models import QuerySet

class Floor(models.TextChoices):
    A = 'A', _('Floor A')
    B = 'B', _('Floor B')
    C = 'C', _('Floor C')
    D = 'D', _('Floor D')

class Side(models.TextChoices):
    LEFT = 'L', _('Left')
    RIGHT = 'R', _('Right')

class BaleStatus(models.TextChoices):
    IN_STOCK = 'InStock', _('In Stock - Available for Collection')
    RESERVED = 'Reserved', _('Reserved - Awaiting Collection')
    COLLECTED = 'Collected', _('Collected by Farmer')
    REMOVED = 'Removed', _('Removed - Damaged/Discarded')

class BaleReason(models.TextChoices):
    RR = 'RR', _('Over/Under Weight')
    MR = 'MR', _('Mixed Hand')
    LR = 'LR', _('Mouldy')
    BGRW = 'BGRW', _('Wet')
    OR = 'OR', _('Hot')
    WR = 'WR', _('Wrong Hessian')
    DR = 'DR', _('Diesel')
    NE = 'NE', _('Nesting')
    GOOD = 'GOOD', _('Good Condition')

class MetricsDict(TypedDict):
    intake: int
    outflow: int
    ratio: float
    net_change: int

class BRRecord(models.Model):
    br_number = models.CharField(_('BR Number'), max_length=30, unique=True, db_index=True)
    sale_date = models.DateField(_('Sale Date'), db_index=True)
    received_date = models.DateTimeField(_('Date Received at TSF'), db_index=True)
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='br_records', null=True, blank=True)
    total_bales = models.PositiveIntegerField(_('Total Bales on BR'), null=True, blank=True)
    total_mass = models.DecimalField(_('Total Mass'), max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sale_date', '-br_number']
        indexes = [models.Index(fields=['sale_date', 'received_date'], name='br_date_idx')]

    def __str__(self) -> str:
        return f"BR {self.br_number} - {self.sale_date}"

class BaleQuerySet(models.QuerySet):
    def in_stock(self) -> QuerySet:
        return self.filter(status=BaleStatus.IN_STOCK)

    def collected(self) -> QuerySet:
        return self.filter(status=BaleStatus.COLLECTED)

    def defects(self) -> QuerySet:
        return self.exclude(reason=BaleReason.GOOD)

    def by_location(self, floor: str, row: int, side: str, level: int) -> QuerySet:
        return self.filter(floor=floor, row=row, side=side, level=level)

    def daily_metrics(self, date) -> Dict[str, Any]:
        qs = self.filter(date_scanned__date=date)
        return qs.aggregate(
            intake=Count('id'),
            intake_mass=Sum('mass'),
            collected=Count('id', filter=Q(status=BaleStatus.COLLECTED)),
            defects=Count('id', filter=~Q(reason=BaleReason.GOOD)),
            avg_dwell=Avg(F('date_collected') - F('date_scanned'), filter=Q(status=BaleStatus.COLLECTED))
        )

    def in_out_ratio(self, start_date, end_date) -> MetricsDict:
        qs = self.filter(br_record__sale_date__range=[start_date, end_date])
        intake = qs.count()
        outflow = qs.filter(date_collected__date__range=[start_date, end_date]).count()
        return MetricsDict(
            intake=intake,
            outflow=outflow,
            ratio=round(outflow / intake, 2) if intake else 0.0,
            net_change=intake - outflow
        )

BaleManager = models.Manager.from_queryset(BaleQuerySet)

class Bale(models.Model):
    """
    Individual tobacco bale. Location = floor + row + side + level.
    Only grower_no, lot_no, mass are mandatory.
    """
    br_record = models.ForeignKey(BRRecord, on_delete=models.PROTECT, related_name='bales', null=True, blank=True)

    # Mandatory fields
    grower_no = models.CharField(_('Grower Number'), max_length=20, db_index=True)
    lot_no = models.CharField(_('Lot Number'), max_length=20, db_index=True)
    mass = models.DecimalField(_('Mass'), max_digits=6, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])

    # Optional fields
    barcode = models.CharField(_('Barcode'), max_length=50, db_index=True, blank=True)
    reason = models.CharField(_('Condition / Reason'), max_length=10, choices=BaleReason.choices, default=BaleReason.GOOD, db_index=True)
    reason_notes = models.CharField(_('Reason Notes'), max_length=200, blank=True)

    # Location fields
    floor = models.CharField(_('Floor'), max_length=1, choices=Floor.choices, default=Floor.A)
    row = models.PositiveSmallIntegerField(_('Row'), validators=[MinValueValidator(1)], default=1)
    side = models.CharField(_('Side'), max_length=1, choices=Side.choices, default=Side.LEFT)
    level = models.PositiveSmallIntegerField(_('Level'), validators=[MinValueValidator(1)], help_text=_('Vertical position in stack, 1 is bottom'), default=1)

    # Status and timestamps
    status = models.CharField(_('Status'), max_length=15, choices=BaleStatus.choices, default=BaleStatus.IN_STOCK, db_index=True)
    date_received = models.DateTimeField(_('Date Received'), null=True, blank=True, db_index=True)
    date_scanned = models.DateTimeField(_('Date Scanned'), auto_now_add=True, db_index=True)
    date_collected = models.DateTimeField(_('Date Collected'), null=True, blank=True, db_index=True)

    # User tracking - optional
    scanned_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='bales_scanned', null=True, blank=True)
    collected_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='bales_collected')

    objects = BaleManager()

    class Meta:
        ordering = ['floor', 'row', 'side', 'level']
        indexes = [
            models.Index(fields=['status', 'floor', 'row', 'side', 'level'], name='bale_location_idx'),
            models.Index(fields=['br_record', 'date_scanned'], name='bale_br_date_idx'),
            models.Index(fields=['grower_no', 'lot_no', 'status'], name='bale_grower_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['floor', 'row', 'side', 'level', 'status'],
                condition=Q(status=BaleStatus.IN_STOCK),
                name='unique_slot_in_stock'
            ),
            models.UniqueConstraint(
                fields=['br_record', 'barcode'],
                name='unique_bale_per_br',
                condition=~Q(barcode='')
            )
        ]

    def __str__(self) -> str:
        return f"{self.barcode or self.id} - {self.grower_no}"

    @property
    def location_display(self) -> str:
        return f"Floor {self.floor} Row {self.row} Side {self.get_side_display()} Level {self.level}"

    @property
    def is_available(self) -> bool:
        return self.status == BaleStatus.IN_STOCK

    @property
    def is_defect(self) -> bool:
        return self.reason!= BaleReason.GOOD

    @transaction.atomic
    def reserve_for_collection(self, user: User = None) -> None:
        if self.status!= BaleStatus.IN_STOCK:
            raise ValidationError(_('Bale not available for collection'))
        self.status = BaleStatus.RESERVED
        self.save(update_fields=['status'])

    @transaction.atomic
    def mark_collected(self, user: User = None) -> None:
        if self.status not in [BaleStatus.IN_STOCK, BaleStatus.RESERVED]:
            raise ValidationError(_('Bale not available for collection'))

        self.status = BaleStatus.COLLECTED
        self.date_collected = timezone.now()
        self.collected_by = user
        self.save(update_fields=['status', 'date_collected', 'collected_by'])

        # Collapse stack levels above this position
        Bale.reorder_levels(self.floor, self.row, self.side)

    @classmethod
    @transaction.atomic
    def reorder_levels(cls, floor: str, row: int, side: str) -> None:
        """
        Collapse stack levels to fill gaps after bale removal.
        Uses floor + row + side only.
        """
        bales = list(
            cls.objects.in_stock()
           .filter(floor=floor, row=row, side=side)
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
        pass

class BaleHistory(models.Model):
    bale = models.ForeignKey(Bale, on_delete=models.CASCADE, related_name='history')
    old_status = models.CharField(max_length=15)
    old_location = models.CharField(max_length=100, blank=True)
    new_status = models.CharField(max_length=15)
    new_location = models.CharField(max_length=100, blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-changed_at']
        indexes = [models.Index(fields=['bale', 'changed_at'], name='history_bale_time_idx')]

    def __str__(self) -> str:
        return f"{self.bale.barcode or self.bale.id}: {self.old_status} → {self.new_status}"
