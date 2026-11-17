# planner/accounts.py
"""
Xác thực email tài khoản.

- Token dùng cơ chế của Django (PasswordResetTokenGenerator): ký bằng
  SECRET_KEY, hết hạn theo PASSWORD_RESET_TIMEOUT, không lưu trong DB.
- Hash gồm trạng thái email_verified và pending_email nên link tự hết
  hiệu lực sau khi đã xác thực hoặc khi người dùng đổi sang email khác.
"""
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import UserProfile


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = 'planner.accounts.EmailVerificationTokenGenerator'

    def _make_hash_value(self, user, timestamp):
        profile = getattr(user, 'profile', None)
        verified = profile.email_verified if profile else True
        pending = profile.pending_email if profile else ''
        return f'{user.pk}{user.email}{pending}{verified}{timestamp}'


email_verification_token = EmailVerificationTokenGenerator()


def mask_email(email):
    """an.nguyen@gmail.com -> an*******@gmail.com"""
    local, _, domain = email.partition('@')
    if not domain:
        return email
    visible = local[:2]
    return f"{visible}{'*' * max(len(local) - len(visible), 3)}@{domain}"


def send_verification_email(request, user, to_email=None):
    """Gửi link xác thực tới to_email (mặc định email của tài khoản)."""
    to_email = to_email or user.email
    path = reverse('verify_email', kwargs={
        'uidb64': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': email_verification_token.make_token(user),
    })
    context = {
        'user': user,
        'verify_url': request.build_absolute_uri(path),
        'is_email_change': bool(user.profile.pending_email),
        'valid_days': settings.PASSWORD_RESET_TIMEOUT // 86400,
    }
    subject = 'Xác thực email tài khoản StudyPlanner'
    if context['is_email_change']:
        subject = 'Xác nhận email mới cho tài khoản StudyPlanner'
    message = EmailMultiAlternatives(
        subject=subject,
        body=render_to_string('planner/emails/verify_email.txt', context),
        to=[to_email],
    )
    message.attach_alternative(
        render_to_string('planner/emails/verify_email.html', context),
        'text/html',
    )
    message.send()


def is_email_verified(user):
    profile = UserProfile.objects.filter(user=user).only('email_verified').first()
    # Tài khoản chưa có hồ sơ (VD tạo bằng createsuperuser) coi như đã xác thực
    return profile is None or profile.email_verified
