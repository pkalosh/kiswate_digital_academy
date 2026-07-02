"""
Audit trail signals. Fires on save/delete for sensitive models.
Actor is null for existing views (no request in signal context); new views log explicitly.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


def _log(model_name, object_id, action, description, school=None):
    from .models import AuditLog
    try:
        AuditLog.objects.create(
            model_name=model_name,
            object_id=object_id,
            action=action,
            description=description,
            school=school,
        )
    except Exception:
        pass  # never break the request for audit logging


def _attendance_school(instance):
    try:
        return instance.enrollment.school
    except Exception:
        return None


@receiver(post_save, sender='school.Attendance')
def audit_attendance_save(sender, instance, created, **kwargs):
    _log(
        'Attendance', instance.pk,
        'create' if created else 'update',
        f"Status={instance.status} student={instance.enrollment.student_id if instance.enrollment_id else '?'}",
        school=_attendance_school(instance),
    )


@receiver(post_delete, sender='school.Attendance')
def audit_attendance_delete(sender, instance, **kwargs):
    _log(
        'Attendance', instance.pk, 'delete',
        f"Deleted attendance status={instance.status}",
        school=_attendance_school(instance),
    )


@receiver(post_save, sender='school.DisciplineRecord')
def audit_discipline_save(sender, instance, created, **kwargs):
    _log(
        'DisciplineRecord', instance.pk,
        'create' if created else 'update',
        f"{instance.get_incident_type_display()} / {instance.get_severity_display()} - {instance.student}",
        school=instance.school,
    )


@receiver(post_delete, sender='school.DisciplineRecord')
def audit_discipline_delete(sender, instance, **kwargs):
    _log('DisciplineRecord', instance.pk, 'delete', f"Deleted for {instance.student}", school=instance.school)


@receiver(post_save, sender='school.Payment')
def audit_payment_save(sender, instance, created, **kwargs):
    _log(
        'Payment', instance.pk,
        'create' if created else 'update',
        f"{instance.get_payment_type_display()} {instance.amount} status={instance.status}",
        school=instance.school,
    )


@receiver(post_delete, sender='school.Payment')
def audit_payment_delete(sender, instance, **kwargs):
    _log('Payment', instance.pk, 'delete', f"Deleted payment {instance.amount}", school=instance.school)
