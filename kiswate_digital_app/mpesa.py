"""
M-Pesa Daraja STK Push utility for DIL payments.

Falls back to TEST MODE (simulated) when credentials are not configured,
so the full payment UI can be exercised in development.
"""

import base64
import logging
import re
from datetime import datetime

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _is_configured():
    return bool(
        getattr(settings, 'MPESA_CONSUMER_KEY', '') and
        getattr(settings, 'MPESA_CONSUMER_SECRET', '') and
        getattr(settings, 'MPESA_PASSKEY', '') and
        getattr(settings, 'MPESA_CALLBACK_URL', '')
    )


def _base_url():
    env = getattr(settings, 'MPESA_ENV', 'sandbox')
    if env == 'production':
        return 'https://api.safaricom.co.ke'
    return 'https://sandbox.safaricom.co.ke'


def get_access_token():
    """Fetch OAuth2 access token from Daraja."""
    import requests
    url = f"{_base_url()}/oauth/v1/generate?grant_type=client_credentials"
    resp = requests.get(
        url,
        auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()['access_token']


def _format_phone(raw: str) -> str:
    """Normalise phone to 254XXXXXXXXX format."""
    digits = re.sub(r'\D', '', raw)
    if digits.startswith('0'):
        digits = '254' + digits[1:]
    elif digits.startswith('+'):
        digits = digits[1:]
    if not digits.startswith('254'):
        digits = '254' + digits
    return digits


def _timestamp() -> str:
    return datetime.now().strftime('%Y%m%d%H%M%S')


def _password(shortcode: str, passkey: str, ts: str) -> str:
    raw = f"{shortcode}{passkey}{ts}"
    return base64.b64encode(raw.encode()).decode()


def initiate_stk_push(phone: str, amount: int, account_ref: str, description: str) -> dict:
    """
    Send an STK push to *phone* for *amount* KES.

    Returns a dict with keys:
      success (bool), checkout_request_id (str), message (str), test_mode (bool)
    """
    if not _is_configured():
        # Test / demo mode — simulate success so UI can be validated
        logger.info("M-Pesa credentials not set — running STK push in TEST MODE")
        return {
            'success': True,
            'test_mode': True,
            'checkout_request_id': f'TEST-{account_ref}-{_timestamp()}',
            'message': 'TEST MODE: STK push simulated. No real charge made.',
        }

    try:
        import requests as _req
        ts = _timestamp()
        shortcode = settings.MPESA_SHORTCODE
        token = get_access_token()
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        payload = {
            'BusinessShortCode': shortcode,
            'Password': _password(shortcode, settings.MPESA_PASSKEY, ts),
            'Timestamp': ts,
            'TransactionType': 'CustomerPayBillOnline',
            'Amount': int(amount),
            'PartyA': _format_phone(phone),
            'PartyB': shortcode,
            'PhoneNumber': _format_phone(phone),
            'CallBackURL': settings.MPESA_CALLBACK_URL,
            'AccountReference': account_ref[:12],
            'TransactionDesc': description[:13],
        }
        resp = _req.post(
            f"{_base_url()}/mpesa/stkpush/v1/processrequest",
            json=payload, headers=headers, timeout=20,
        )
        data = resp.json()
        if data.get('ResponseCode') == '0':
            return {
                'success': True,
                'test_mode': False,
                'checkout_request_id': data.get('CheckoutRequestID', ''),
                'message': data.get('CustomerMessage', 'STK push sent. Check your phone.'),
            }
        return {
            'success': False,
            'test_mode': False,
            'checkout_request_id': '',
            'message': data.get('errorMessage') or data.get('ResponseDescription', 'STK push failed.'),
        }
    except Exception as exc:
        logger.error("STK push error: %s", exc)
        return {'success': False, 'test_mode': False, 'checkout_request_id': '', 'message': str(exc)}
