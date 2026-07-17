"""
send_dil_reminders — dispatch pending DIL NotificationLog entries.

Processes NotificationLog records with status='pending', fires them via
the EUJIM SMS gateway and/or Django email depending on notification_type,
then updates each record's status to 'sent' or 'failed'.

Run every minute via cron:
    * * * * * /path/to/venv/bin/python manage.py send_dil_reminders >> /var/log/kiswate/dil_reminders.log 2>&1
"""
import time
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from kiswate_digital_app.models import NotificationLog


SMS_URL = getattr(settings, 'SMS_API_URL', 'https://quicksms.advantasms.com/api/services/sendsms/')


def _phone_ke(phone: str) -> str:
    p = str(phone).strip().replace(' ', '').replace('-', '')
    if p.startswith('0'):
        return '254' + p[1:]
    if p.startswith('+254'):
        return p[1:]
    if not p.startswith('254'):
        return '254' + p
    return p


def _send_sms(phone: str, message: str) -> tuple:
    """Returns (success: bool, error: str)."""
    api_key = getattr(settings, 'SMS_API_KEY', '')
    partner = getattr(settings, 'SMS_PARTNERID', '')
    shortcode = getattr(settings, 'SMS_SHORTCODE', '')
    if not all([api_key, partner, shortcode]):
        return False, 'SMS credentials not configured'
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
                    return True, ''
        except requests.exceptions.RequestException as e:
            err = str(e)
        if attempt < 2:
            time.sleep(3)
    return False, err if 'err' in dir() else 'SMS send failed after retries'


def _send_email(to: str, subject: str, body: str) -> tuple:
    """Returns (success: bool, error: str)."""
    if not to:
        return False, 'No email address'
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
        return True, ''
    except Exception as e:
        return False, str(e)


class Command(BaseCommand):
    help = 'Dispatch pending DIL NotificationLog entries via SMS and/or email.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=100,
            help='Max notifications to process per run (default 100).'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        pending = NotificationLog.objects.filter(
            status='pending'
        ).select_related('recipient').order_by('created_at')[:limit]

        if not pending.exists():
            self.stdout.write('No pending DIL notifications.')
            return

        sent = failed = 0

        for log in pending:
            profile = log.recipient
            phone = getattr(profile, 'phone', '') or ''
            email = profile.user.email if profile.user_id else ''
            n_type = log.notification_type  # 'sms', 'email', 'both'
            subject = log.subject or 'Kiswate DIL Notification'
            message = log.message or ''

            if not message:
                log.status = 'failed'
                log.error_message = 'Empty message body'
                log.save(update_fields=['status', 'error_message'])
                failed += 1
                continue

            ok = False
            errors = []

            if n_type in ('sms', 'both') and phone:
                success, err = _send_sms(phone, message)
                if success:
                    ok = True
                else:
                    errors.append(f'SMS: {err}')

            if n_type in ('email', 'both') and email:
                success, err = _send_email(email, subject, message)
                if success:
                    ok = True
                else:
                    errors.append(f'Email: {err}')

            if ok:
                log.status = 'sent'
                log.sent_at = timezone.now()
                log.error_message = ''
                sent += 1
            else:
                log.status = 'failed'
                log.error_message = '; '.join(errors) or 'No contact method available'
                failed += 1

            log.save(update_fields=['status', 'sent_at', 'error_message'])

        self.stdout.write(
            self.style.SUCCESS(
                f'DIL reminders done — sent: {sent}, failed: {failed}'
            )
        )
