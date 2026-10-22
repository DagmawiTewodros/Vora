"""Generic audit trail: register a model and every save/delete is logged."""

import datetime
import decimal
import uuid

from django.db.models.signals import post_delete, post_save, pre_save

from .middleware import get_current_user

_registered = set()


def _jsonable(value):
    if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
        return value.isoformat()
    if isinstance(value, (decimal.Decimal, uuid.UUID)):
        return str(value)
    return value


def snapshot(instance):
    data = {}
    for field in instance._meta.concrete_fields:
        if field.name in ("password", "pin_hash"):
            continue
        data[field.attname] = _jsonable(getattr(instance, field.attname))
    return data


def log(action, instance=None, *, model=None, object_id="", description="", before=None, after=None, user=None):
    from .models import AuditLog

    AuditLog.objects.create(
        user=user or get_current_user(),
        action=action,
        model=model or (instance._meta.label if instance is not None else ""),
        object_id=str(object_id or (instance.pk if instance is not None else "")),
        description=description[:255],
        before=before,
        after=after,
    )


def _pre_save(sender, instance, **kwargs):
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).first()
        instance._audit_before = snapshot(old) if old else None
    else:
        instance._audit_before = None


def _post_save(sender, instance, created, **kwargs):
    before = getattr(instance, "_audit_before", None)
    after = snapshot(instance)
    if not created and before == after:
        return
    if not created and before:
        changed = {k for k in after if before.get(k) != after[k]}
        before = {k: before.get(k) for k in changed}
        after = {k: after[k] for k in changed}
    log("create" if created else "update", instance, before=before, after=after)


def _post_delete(sender, instance, **kwargs):
    log("delete", instance, before=snapshot(instance))


def register(*models):
    for model in models:
        if model in _registered:
            continue
        _registered.add(model)
        uid = f"audit-{model._meta.label}"
        pre_save.connect(_pre_save, sender=model, dispatch_uid=uid + "-pre")
        post_save.connect(_post_save, sender=model, dispatch_uid=uid + "-post")
        post_delete.connect(_post_delete, sender=model, dispatch_uid=uid + "-del")
