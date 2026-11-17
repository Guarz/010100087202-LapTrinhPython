# planner/email_backends.py
"""
Django email backend gửi qua Brevo Transactional Email API (HTTPS).

Dùng API thay cho SMTP vì nhiều nền tảng deploy (gói free) chặn cổng SMTP.
Mọi chỗ gọi send_mail / EmailMessage trong Django tự đi qua backend này
khi settings.EMAIL_BACKEND = 'planner.email_backends.BrevoApiBackend'.

Cần: BREVO_API_KEY và DEFAULT_FROM_EMAIL là một sender đã xác minh trên Brevo.
"""
import base64
import json
import logging
import urllib.error
import urllib.request
from email.utils import getaddresses, parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_API_URL = 'https://api.brevo.com/v3/smtp/email'


def _contact(address):
    return _contact_from(*parseaddr(address))


def _contacts(addresses):
    return [_contact_from(name, email) for name, email in getaddresses(addresses)]


def _contact_from(name, email):
    contact = {'email': email}
    if name:
        contact['name'] = name
    return contact


def build_payload(message):
    """Chuyển một EmailMessage của Django thành JSON cho Brevo API."""
    payload = {
        'sender': _contact(message.from_email or settings.DEFAULT_FROM_EMAIL),
        'to': _contacts(message.to),
        'subject': message.subject,
        'textContent': message.body,
    }
    if message.cc:
        payload['cc'] = _contacts(message.cc)
    if message.bcc:
        payload['bcc'] = _contacts(message.bcc)
    if message.reply_to:
        payload['replyTo'] = _contact(message.reply_to[0])
    for content, mimetype in getattr(message, 'alternatives', []):
        if mimetype == 'text/html':
            payload['htmlContent'] = content
    attachments = []
    for attachment in message.attachments:
        # Bỏ qua MIMEBase tự dựng; chỉ hỗ trợ (tên, nội dung, mimetype)
        if not isinstance(attachment, tuple):
            continue
        filename, content, _mimetype = attachment
        if isinstance(content, str):
            content = content.encode('utf-8')
        attachments.append({'name': filename, 'content': base64.b64encode(content).decode('ascii')})
    if attachments:
        payload['attachment'] = attachments
    return payload


class BrevoApiBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, api_key=None, timeout=10, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = api_key or getattr(settings, 'BREVO_API_KEY', '')
        self.timeout = timeout

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            if not message.recipients():
                continue
            try:
                self._send(message)
                sent += 1
            except Exception:
                logger.exception('Brevo: gửi email tới %s thất bại', message.to)
                if not self.fail_silently:
                    raise
        return sent

    def _send(self, message):
        if not self.api_key:
            raise RuntimeError('Chưa cấu hình BREVO_API_KEY.')
        request = urllib.request.Request(
            BREVO_API_URL,
            data=json.dumps(build_payload(message)).encode('utf-8'),
            headers={
                'api-key': self.api_key,
                'accept': 'application/json',
                'content-type': 'application/json',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read() or b'{}')
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', 'replace')
            raise RuntimeError(f'Brevo trả lỗi {exc.code}: {detail}') from exc
