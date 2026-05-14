"""
Signal handlers for BR Bale Tracker audit logging.

This module logs every meaningful change to `Bale` instances into `BaleHistory`.
Logging happens in `post_save` to ensure the main transaction succeeds first.

Design decisions:
1. Use `pre_save` to snapshot old state on the instance as a private attribute.
2. Use `post_save` to compare old vs new state and create history only if needed.
3. Ignore no-op saves to avoid spam in the audit trail.
4. Never raise exceptions in signals - log and fail silently to avoid breaking the main flow.
"""

from __future__ import annotations
import logging
from typing import Optional, TYPE_CHECKING

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

if TYPE_CHECKING:
    from.models import Bale

from.models import Bale, BaleHistory

logger = logging.getLogger(__name__)

_STATE_ATTR_STATUS = '_old_status'
_STATE_ATTR_LOCATION = '_old_location'

@receiver(pre_save, sender=Bale)
def capture_old_bale_state(sender, instance: Bale, **kwargs) -> None:
    """
    Snapshot pre-save state of a Bale instance.

    Stores old status and location on the instance as private attributes.
    These are used in `log_bale_change` to avoid unnecessary history records.

    Args:
        sender: The Bale model class.
        instance: The Bale instance being saved.
    """
    if not instance.pk:
        # New instance: no old state exists
        setattr(instance, _STATE_ATTR_STATUS, None)
        setattr(instance, _STATE_ATTR_LOCATION, None)
        return

    try:
        old = Bale.objects.only('status', 'floor', 'stack', 'row', 'side', 'level').get(pk=instance.pk)
        setattr(instance, _STATE_ATTR_STATUS, old.status)
        setattr(instance, _STATE_ATTR_LOCATION, old.location_display)
    except Bale.DoesNotExist:
        setattr(instance, _STATE_ATTR_STATUS, None)
        setattr(instance, _STATE_ATTR_LOCATION, None)
    except Exception as e:
        logger.error("Failed to capture old state for Bale %s: %s", instance.pk, e)
        setattr(instance, _STATE_ATTR_STATUS, None)
        setattr(instance, _STATE_ATTR_LOCATION, None)

@receiver(post_save, sender=Bale)
def log_bale_change(sender, instance: Bale, created: bool, **kwargs) -> None:
    """
    Create a BaleHistory record if status or location changed.

    A history record is created when:
    1. The bale is newly created, OR
    2. The status changed, OR
    3. The location changed

    The `changed_by` field uses `collected_by` if present, otherwise `scanned_by`.
    This ensures the responsible user is always recorded.

    Args:
        sender: The Bale model class.
        instance: The Bale instance after save.
        created: True if this is a new instance.
    """
    old_status: Optional[str] = getattr(instance, _STATE_ATTR_STATUS, None)
    old_location: Optional[str] = getattr(instance, _STATE_ATTR_LOCATION, None)

    status_changed = old_status!= instance.status
    location_changed = old_location!= instance.location_display

    if not (created or status_changed or location_changed):
        return

    changed_by = instance.collected_by or instance.scanned_by
    if not changed_by:
        logger.warning(
            "BaleHistory not created for Bale %s: no user found in collected_by or scanned_by",
            instance.pk
        )
        return

    try:
        BaleHistory.objects.create(
            bale=instance,
            old_status=old_status or '',
            old_location=old_location or '',
            new_status=instance.status,
            new_location=instance.location_display,
            changed_by=changed_by,
            notes='Auto-logged on save'
        )
    except Exception as e:
        logger.error("Failed to create BaleHistory for Bale %s: %s", instance.pk, e)
