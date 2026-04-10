from app import db
from app.auth import auth_service
from app.models import User


def create_user(
    email='user@example.com',
    password='Testpassword1',
    verified=False,
):
    user = User()
    user.first_name = 'Test'
    user.last_name = 'User'
    user.email = email
    user.email_verified = verified
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def test_authenticate_user_success(app, monkeypatch):
    create_user(
        email='user@example.com',
        password='Testpassword1',
        verified=True,
    )

    def noop_log(*args, **kwargs):
        return None

    monkeypatch.setattr(auth_service, "log_security_event", noop_log)
    monkeypatch.setattr(auth_service, "log_user_action", noop_log)

    with app.test_request_context(
        "/", environ_base={"REMOTE_ADDR": "127.0.0.1"}
    ):
        user = auth_service.authenticate_user(
            "  USER@EXAMPLE.COM  ", "Testpassword1"
        )
    assert user is not None
    assert user.email == "user@example.com"


def test_authenticate_user_invalid_credentials(app, monkeypatch):
    create_user(
        email='user@example.com',
        password='Testpassword1',
        verified=True,
    )

    def noop_log(*args, **kwargs):
        return None

    monkeypatch.setattr(auth_service, "log_security_event", noop_log)
    monkeypatch.setattr(auth_service, "log_user_action", noop_log)

    with app.test_request_context(
        "/", environ_base={"REMOTE_ADDR": "127.0.0.1"}
    ):
        user = auth_service.authenticate_user(
            "user@example.com", "WrongPassword1"
        )
    assert user is None


def test_register_user_creates_user(app, monkeypatch):
    def noop_send_verification_email(user):
        return None

    def noop_log(*args, **kwargs):
        return None

    monkeypatch.setattr(
        auth_service,
        "send_verification_email",
        noop_send_verification_email,
    )
    monkeypatch.setattr(auth_service, "log_user_action", noop_log)

    with app.test_request_context(
        "/", environ_base={"REMOTE_ADDR": "127.0.0.1"}
    ):
        user = auth_service.register_user(
            first_name="Jane",
            last_name="Doe",
            email="JANE@EXAMPLE.COM",
            password="Testpassword1",
        )
    assert user.id is not None
    assert user.email == "jane@example.com"
    assert user.check_password("Testpassword1") is True


def test_request_password_reset_calls_email_for_existing_user(
    app, monkeypatch
):
    create_user(email='reset@example.com', password='Testpassword1')
    called = {}

    def fake_send_reset_password_email(user):
        called["user_id"] = user.id

    monkeypatch.setattr(
        auth_service,
        "send_reset_password_email",
        fake_send_reset_password_email,
    )
    auth_service.request_password_reset("reset@example.com")
    assert "user_id" in called


def test_request_password_reset_noop_for_missing_user(app, monkeypatch):
    called = {"count": 0}

    def fake_send_reset_password_email(user):
        called["count"] += 1

    monkeypatch.setattr(
        auth_service,
        "send_reset_password_email",
        fake_send_reset_password_email,
    )
    auth_service.request_password_reset("missing@example.com")
    assert called["count"] == 0


def test_complete_password_reset_updates_password(app):
    user = create_user(
        email='pw@example.com', password='Oldpassword1'
    )
    auth_service.complete_password_reset(user, "Newpassword1")
    db.session.refresh(user)
    assert user.check_password("Newpassword1") is True


def test_verify_email_with_token_invalid(app, monkeypatch):
    def fake_verify_token(token, token_type):
        return None

    monkeypatch.setattr(
        User,
        "verify_token",
        staticmethod(fake_verify_token),
    )
    outcome = auth_service.verify_email_with_token("bad-token")
    assert outcome == "invalid"


def test_verify_email_with_token_already_verified(app, monkeypatch):
    user = create_user(
        email='verified@example.com', verified=True
    )

    def fake_verify_token(token, token_type):
        return user

    monkeypatch.setattr(
        User,
        "verify_token",
        staticmethod(fake_verify_token),
    )
    outcome = auth_service.verify_email_with_token("token")
    assert outcome == "already_verified"


def test_verify_email_with_token_success(app, monkeypatch):
    user = create_user(
        email='verify@example.com', verified=False
    )

    def fake_verify_token(token, token_type):
        return user

    monkeypatch.setattr(
        User,
        "verify_token",
        staticmethod(fake_verify_token),
    )
    outcome = auth_service.verify_email_with_token("token")
    db.session.refresh(user)
    assert outcome == "verified"
    assert user.email_verified is True


def test_verification_reminder_warns_invalid_email(app):
    user = create_user(email='warn@example.com', verified=False)
    user.email = ""
    db.session.commit()
    warn = (
        auth_service.verification_reminder_should_warn_invalid_email(
            user
        )
    )
    assert warn is True


def test_verification_reminder_ok_for_valid_email(app):
    user = create_user(email='ok@example.com', verified=False)
    warn = (
        auth_service.verification_reminder_should_warn_invalid_email(
            user
        )
    )
    assert warn is False


def test_resend_verification_invalid_email(app):
    user = create_user(email='ok@example.com', verified=False)
    user.email = "   "
    db.session.commit()
    outcome = auth_service.resend_verification_email(user)
    assert outcome == "invalid_email"


def test_resend_verification_send_failed(app, monkeypatch):
    user = create_user(email='fail@example.com', verified=False)

    def raise_error(u):
        raise RuntimeError("send failed")

    monkeypatch.setattr(
        auth_service,
        "send_verification_email",
        raise_error,
    )
    outcome = auth_service.resend_verification_email(user)
    assert outcome == "send_failed"


def test_resend_verification_success(app, monkeypatch):
    user = create_user(email='ok@example.com', verified=False)

    def noop(u):
        return None

    monkeypatch.setattr(
        auth_service,
        "send_verification_email",
        noop,
    )
    outcome = auth_service.resend_verification_email(user)
    assert outcome == "success"
