"""
send_notifications — dispatch pending school SMS notifications.

Processes queued Notification records that have an sms_status of 'pending'
and fires them via the EUJIM SMS gateway.  Email notifications are sent
via Django's send_mail.

Run every minute via cron:
    * * * * * /path/to/venv/bin/python manage.py send_notifications >> /var/log/kiswate/sms.log 2>&1
"""
import time
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import send_mail
from school.models import Notification, Parent, StaffProfile


SMS_URL = getattr(settings, 'SMS_API_URL', 'https://quicksms.advantasms.com/api/services/sendsms/')


def _phone_ke(phone: str) -> str:
    """Normalise phone to 254XXXXXXXXX format."""
    p = str(phone).strip().replace(' ', '').replace('-', '')
    if p.startswith('0'):
        return '254' + p[1:]
    if p.startswith('+254'):
        return p[1:]
    if not p.startswith('254'):
        return '254' + p
    return p


def _sms(phone: str, message: str) -> bool:
    api_key = getattr(settings, 'SMS_API_KEY', '')
    partner = getattr(settings, 'SMS_PARTNERID', '')
    shortcode = getattr(settings, 'SMS_SHORTCODE', '')
    if not all([api_key, partner, shortcode]):
        return False
    payload = {
        'apikey': api_key,
        'partnerID': partner,
        'shortcode': shortcode,
        'message': message,
        'mobile': _phone_ke(phone),
    }
    for attempt in range(3):
        try:
            r = requests.post(SMS_URL, json=payload, timeout=15)
            if r.status_code == 200:
                data = r.json()
                resp = data.get('responses', [{}])[0]
                if resp.get('response-code') == 200:
                    return True
        except requests.exceptions.RequestException:
            pass
        if attempt < 2:
            time.sleep(3)
    return False


def _email(to: str, subject: str, body: str) -> bool:
    if not to:
        return False
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
        return True
    except Exception:
        return False


class Command(BaseCommand):
    help = 'Dispatch pending school Notification SMS/email messages.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=50,
            help='Max notifications to process per run (default 50).'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        # Fetch notifications that haven't been delivered via SMS yet.
        # We use a convention: Notification.is_read=False means undelivered.
        # Only process notifications that also have an sms_pending flag or
        # that were created by the system (title not null) in the last 24h.
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(hours=24)

        pending = Notification.objects.filter(
            is_read=False,
            sent_at__gte=since,
        ).select_related('recipient').order_by('sent_at')[:limit]

        if not pending.exists():
            self.stdout.write('No pending notifications.')
            return

        sent_sms = 0
        sent_email = 0
        failed = 0

        for notif in pending:
            user = notif.recipient
            subject_line = notif.title or 'Kiswate Notification'
            body = notif.message or ''
            if not body:
                continue

            # Resolve phone number
            phone = getattr(user, 'phone_number', '') or ''
            email = getattr(user, 'email', '') or ''

            # Try phone via profile relations
            if not phone:
                staff = getattr(user, 'staffprofile', None)
                if staff:
                    phone = getattr(staff, 'phone', '') or ''
                parent = getattr(user, 'parent', None)
                if parent:
                    phone = getattr(parent, 'phone', '') or phone

            ok_sms = False
            ok_email = False

            if phone:
                ok_sms = _sms(phone, f"{subject_line}: {body}")
                if ok_sms:
                    sent_sms += 1

            if email:
                ok_email = _email(email, subject_line, body)
                if ok_email:
                    sent_email += 1

            if not ok_sms and not ok_email:
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Done — SMS sent: {sent_sms}, Email sent: {sent_email}, Failed: {failed}'
            )
        )
