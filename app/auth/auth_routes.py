import sqlalchemy as sa

from flask import (
    current_app,
    flash,
    redirect,
    render_template,
    url_for,
    request,
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)

from app import db
from app.auth import bp
from app.auth.auth_emails import (
    send_reset_password_email,
    send_verification_email,
)
from app.auth.auth_forms import (
    ForgotPasswordForm,
    LoginForm,
    RegistrationForm,
    ResetPasswordForm,
)
from app.models import User
from app.utils.logger import (
    log_info,
    log_warning,
    log_security_event,
    log_user_action,
)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.email_verified:
            return redirect(url_for('main.index'))
        else:
            return redirect(url_for('auth.verification_reminder'))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.email == form.email.data.lower()))
        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password', category='warning')
            log_security_event(
                'login_failed',
                ip_address=request.remote_addr,
                email=form.email.data
            )
            return redirect(url_for('auth.login'))

        login_user(user, remember=form.remember_me.data)
        log_user_action(
            'login_successful',
            user_id=user.id,
            email=user.email,
            ip_address=request.remote_addr
        )

        # Redirect based on email verification status
        if user.email_verified:
            return redirect(url_for('main.index'))
        else:
            return redirect(url_for('auth.verification_reminder'))

    return render_template('auth/login.html', title='Sign In', form=form)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    # if the user is already logged in, redirect to the index page
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    # create a new instance of the RegistrationForm
    form = RegistrationForm()
    # if the form is submitted
    if form.validate_on_submit():
        # create a new user
        user = User()
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.email = form.email.data.lower()
        # set the password for the user
        user.set_password(form.password.data)
        # add the user to the database
        db.session.add(user)
        db.session.commit()
        send_verification_email(user)

        # Log the user in after registration
        login_user(user)
        
        log_user_action(
            'user_registered',
            user_id=user.id,
            email=user.email,
            ip_address=request.remote_addr
        )

        # flash a message to the user
        flash(
            'Account created successfully! '
            'Please check your email to verify your account.',
            category='success'
        )

        # redirect the user to verification reminder
        return redirect(url_for('auth.verification_reminder'))
    # render the register template
    return render_template('auth/register.html', title='Register', form=form)


@bp.route('/logout')
@login_required
def logout():
    if current_user.is_authenticated:
        log_user_action(
            'logout',
            user_id=current_user.id,
            email=current_user.email,
            ip_address=request.remote_addr
        )
        logout_user()
    return redirect(url_for('main.index'))


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.email == form.email.data.lower()))
        if user:
            current_app.logger.info(
                f'Sending reset password email to user: {user.id},'
                f' email: {user.email}')
            send_reset_password_email(user)
        flash((
            'If the email address you provided is associated with an account, '
            'you will receive an email with instructions on how to reset your '
            'password.'
        ), category='success')
        return redirect(url_for('auth.login'))
    return render_template('auth/forgot_password.html', form=form)


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):

    # if the user is already logged in, redirect to the index page
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # decode the token
    user = User.verify_token(token, token_type='reset_password')
    # if the token is invalid
    if user is None:
        flash('Invalid or expired token', category='warning')
        return redirect(url_for('auth.login'))

    # create a new instance of the ResetPasswordForm
    form = ResetPasswordForm()
    # if the form is submitted
    if form.validate_on_submit():
        # set the password for the user
        user.set_password(form.password.data)
        # add the user to the database
        db.session.commit()
        # flash a message to the user
        flash('Your password has been reset.')
        # redirect the user to the login page
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form, token=token)


@bp.route('/verify_email/<token>')
def verify_email(token):
    user = User.verify_token(token, token_type='verify_email')
    if user is None:
        flash('Invalid or expired token', category='warning')
        return redirect(url_for('auth.login'))

    if user.email_verified is True:
        flash("Your email is verified", category='info')
        return redirect(url_for('auth.login'))

    user.email_verified = True
    db.session.commit()
    flash('Your email has been verified.', category='success')
    return redirect(url_for('auth.login'))


@bp.route('/verification-reminder')
def verification_reminder():
    """
    Show a page reminding users to verify their email address.
    This route is accessible to logged-in users who haven't verified their email.
    """
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    if current_user.email_verified:
        return redirect(url_for('main.index'))

    # Debug logging
    current_app.logger.info(f'Verification reminder for user {current_user.id}, email: {current_user.email}')
    
    # Check if user has a valid email
    if not current_user.email or not current_user.email.strip():
        current_app.logger.error(f'User {current_user.id} has invalid email: {current_user.email}')
        flash('Your account has an invalid email address. Please contact support.', 'error')

    return render_template('auth/verification_reminder.html', title='Verify Your Email')


@bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """
    Resend verification email to the current user.
    """
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    if current_user.email_verified:
        flash('Your email is already verified!', category='info')
        return redirect(url_for('main.index'))

    try:
        # current_user is guaranteed to be authenticated here
        user = User.query.get_or_404(current_user.id)
        
        # Validate email before sending
        if not user.email or not user.email.strip():
            current_app.logger.error(f'User {user.id} has invalid email: {user.email}')
            flash('Your account has an invalid email address. Please contact support.', 'error')
            return redirect(url_for('auth.verification_reminder'))
        
        # Log the email being sent for debugging
        current_app.logger.info(f'Sending verification email to user {user.id} at {user.email}')
        
        send_verification_email(user)
        flash('Verification email sent! Please check your inbox.',
              category='success')
    except Exception as e:
        current_app.logger.error(f'Failed to send verification email: {e}')
        flash('Failed to send verification email. Please try again later.',
              category='error')

    return redirect(url_for('auth.verification_reminder'))
