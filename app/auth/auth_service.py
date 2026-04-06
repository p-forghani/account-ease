import sqlalchemy as sa
from typing import Literal

from flask import current_app, request

from app import db
from app.auth.auth_emails import (
    send_reset_password_email,
    send_verification_email,
)
from app.models import User
from app.utils.logger import log_security_event, log_user_action


def authenticate_user(email: str, password: str) -> User | None:
    """Return the user if credentials are valid; otherwise None."""
    email = email.strip().lower()
    user = db.session.scalar(
        sa.select(User).where(User.email == email)
    )
    if user is None or not user.check_password(password):
        log_security_event(
            'login_failed',
            ip_address=request.remote_addr,
            email=email,
        )
        return None
    log_user_action(
        'login_successful_with_credentials',
        user_id=user.id,
        email=user.email,
        ip_address=request.remote_addr
    )
    return user


def register_user(
    first_name: str,
    last_name: str,
    email: str,
    password: str
) -> User:
    """Register a new user."""
    user = User()
    user.first_name = first_name
    user.last_name = last_name
    user.email = email.strip().lower()
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    send_verification_email(user)
    log_user_action(
        'user_registered',
        user_id=user.id,
        email=user.email,
        ip_address=request.remote_addr
    )

    return user


def log_user_logout(user: User) -> None:
    """Log user logout."""
    log_user_action(
        'logout',
        user_id=user.id,
        email=user.email.strip().lower(),
        ip_address=request.remote_addr
    )


def request_password_reset(email: str) -> None:
    """
    If an account exists for email, send reset mail.
    Same outcome from outside whether or not user exists.
    """
    normalized = email.strip().lower()
    user = db.session.scalar(
        sa.select(User).where(User.email == normalized)
    )
    if user:
        current_app.logger.info(
            'Sending reset password email to user: %s, email: %s',
            user.id,
            user.email,
        )
        send_reset_password_email(user)


def user_from_reset_password_token(token: str) -> User | None:
    """Resolve user from password-reset token, or None if invalid."""
    return User.verify_token(token, token_type='reset_password')


def complete_password_reset(user: User, new_password: str) -> None:
    """Persist new password for user."""
    user.set_password(new_password)
    db.session.commit()


def verify_email_with_token(
    token: str,
) -> Literal['invalid', 'already_verified', 'verified']:
    """Apply email verification from token; return outcome code."""
    user = User.verify_token(token, token_type='verify_email')
    if user is None:
        return 'invalid'
    if user.email_verified:
        return 'already_verified'
    user.email_verified = True
    db.session.commit()
    return 'verified'


def verification_reminder_should_warn_invalid_email(user: User) -> bool:
    """
    Log verification reminder view.
    Return True if UI should show invalid-email / support message.
    """
    current_app.logger.info(
        'Verification reminder for user %s, email: %s',
        user.id,
        user.email,
    )
    if not user.email or not user.email.strip():
        current_app.logger.error(
            'User %s has invalid email: %s',
            user.id,
            user.email,
        )
        return True
    return False


def resend_verification_email(
    user: User,
) -> Literal['success', 'invalid_email', 'send_failed']:
    """Send verification email again; return outcome for messaging."""
    if not user.email or not user.email.strip():
        current_app.logger.error(
            'User %s has invalid email: %s',
            user.id,
            user.email,
        )
        return 'invalid_email'
    try:
        current_app.logger.info(
            'Sending verification email to user %s at %s',
            user.id,
            user.email,
        )
        send_verification_email(user)
        return 'success'
    except Exception as exc:
        current_app.logger.error(
            'Failed to send verification email: %s',
            exc,
        )
        return 'send_failed'
