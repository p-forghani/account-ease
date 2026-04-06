from typing import cast

from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth import bp
from app.auth.auth_forms import (ForgotPasswordForm, LoginForm,
                                 RegistrationForm, ResetPasswordForm)
from app.auth.auth_service import (
    authenticate_user,
    complete_password_reset,
    log_user_logout,
    register_user,
    request_password_reset,
    resend_verification_email,
    user_from_reset_password_token,
    verification_reminder_should_warn_invalid_email,
    verify_email_with_token,
)
from app.models import User


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.email_verified:
            return redirect(url_for('main.index'))
        else:
            return redirect(url_for('auth.verification_reminder'))

    form = LoginForm()
    if form.validate_on_submit():
        if form.email.data is None or form.password.data is None:
            flash('Email and password are required', category='warning')
            return redirect(url_for('auth.login'))

        user = authenticate_user(form.email.data, form.password.data)
        if user is None:
            flash('Invalid email or password', category='warning')
            return redirect(url_for('auth.login'))

        login_user(user, remember=form.remember_me.data)
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
        if (form.first_name.data is None or form.last_name.data is None
                or form.email.data is None or form.password.data is None):
            flash('All fields are required', category='warning')
            return redirect(url_for('auth.register'))
        user = register_user(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            password=form.password.data
        )
        login_user(user)
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
        log_user_logout(user=cast(User, current_user))
        logout_user()
    return redirect(url_for('main.index'))


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        if form.email.data is None:
            flash('Email is required', category='warning')
            return redirect(url_for('auth.forgot_password'))
        request_password_reset(form.email.data)
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
    user = user_from_reset_password_token(token)
    # if the token is invalid
    if user is None:
        flash('Invalid or expired token', category='warning')
        return redirect(url_for('auth.login'))

    # create a new instance of the ResetPasswordForm
    form = ResetPasswordForm()
    # if the form is submitted
    if form.validate_on_submit():
        if form.password.data is None:
            flash('Password is required', category='warning')
            return redirect(url_for('auth.reset_password', token=token))
        complete_password_reset(user, form.password.data)
        # flash a message to the user
        flash('Your password has been reset.')
        # redirect the user to the login page
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', form=form, token=token)


@bp.route('/verify_email/<token>')
def verify_email(token):
    outcome = verify_email_with_token(token)
    if outcome == 'invalid':
        flash('Invalid or expired token', category='warning')
        return redirect(url_for('auth.login'))

    if outcome == 'already_verified':
        flash("Your email is verified", category='info')
        return redirect(url_for('auth.login'))

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

    if verification_reminder_should_warn_invalid_email(cast(User, current_user)):
        flash(
            'Your account has an invalid email address. '
            'Please contact support.',
            'error'
        )

    return render_template(
        'auth/verification_reminder.html',
        title='Verify Your Email'
    )


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

    user = User.query.get_or_404(current_user.id)
    outcome = resend_verification_email(user)

    if outcome == 'invalid_email':
        flash(
            'Your account has an invalid email address. '
            'Please contact support.',
            'error'
        )
    elif outcome == 'send_failed':
        flash(
            'Failed to send verification email. Please try again later.',
            category='error'
        )
    else:
        flash(
            'Verification email sent! Please check your inbox.',
            category='success'
        )

    return redirect(url_for('auth.verification_reminder'))
