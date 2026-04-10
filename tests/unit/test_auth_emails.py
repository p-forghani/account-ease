from app.auth import auth_emails
from app.models import User


class DummyEmailClient:
    def __init__(self):
        self.sent = []

    def send_email(
        self,
        to_emails,
        subject,
        html_content=None,
        text_content=None,
        sync=False,
    ):
        self.sent.append(
            {
                "to_emails": to_emails,
                "subject": subject,
                "html_content": html_content,
                "text_content": text_content,
                "sync": sync,
            }
        )
        return True


def make_user(email="user@example.com"):
    user = User()
    user.first_name = "Test"
    user.last_name = "User"
    user.email = email
    user.password_hash = "hashed"
    return user


def test_send_reset_password_email_raises_without_email(app):
    user = make_user(email="")
    with app.app_context():
        try:
            auth_emails.send_reset_password_email(user)
            assert False, "Expected ValueError for missing email"
        except ValueError:
            assert True


def test_send_verification_email_raises_without_email(app):
    user = make_user(email=None)  # type: ignore
    with app.app_context():
        try:
            auth_emails.send_verification_email(user)
            assert False, "Expected ValueError for missing email"
        except ValueError:
            assert True


def test_send_reset_password_email_sends(monkeypatch, app):
    dummy = DummyEmailClient()

    def fake_generate_token(self, token_type):
        assert token_type == "reset_password"
        return "reset-token"

    monkeypatch.setattr(
        auth_emails, "email_client", dummy
    )
    monkeypatch.setattr(
        User, "generate_token", fake_generate_token
    )

    with app.app_context():
        user = make_user(email="reset@example.com")
        auth_emails.send_reset_password_email(user)

    assert len(dummy.sent) == 1
    assert dummy.sent[0]["to_emails"] == "reset@example.com"
    assert dummy.sent[0]["subject"] == "Reset Password"


def test_send_verification_email_sends(monkeypatch, app):
    dummy = DummyEmailClient()

    def fake_generate_token(self, token_type):
        assert token_type == "verify_email"
        return "verify-token"

    monkeypatch.setattr(
        auth_emails, "email_client", dummy
    )
    monkeypatch.setattr(
        User, "generate_token", fake_generate_token
    )

    with app.app_context():
        user = make_user(email="verify@example.com")
        auth_emails.send_verification_email(user)

    assert len(dummy.sent) == 1
    assert dummy.sent[0]["to_emails"] == "verify@example.com"
    assert dummy.sent[0]["subject"] == "Verify your email"
