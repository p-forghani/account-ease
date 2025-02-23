from flask import current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.clients import bp
from app.clients.forms import CreateClientForm
from app.models import Client


@bp.route('/')
@login_required
def index():
    "Show the list of clients"
    current_app.logger.info('Index route called')
    clients = Client.query.filter_by(user_id=current_user.id).all()
    # TODO: Render a template for this route
    return [client.name for client in clients]


@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    "Add a new client"
    form = CreateClientForm()
    if form.validate_on_submit():
        client = Client(
            name=form.name.data,
            address=form.address.data,
            phone=form.phone.data,
            email=form.email.data,
            user_id=current_user.id
        )
        db.session.add(client)
        db.session.commit()
        flash('Client added successfully')
        return redirect(url_for('clients.index'))
    # Show the form
    return render_template('clients/add.html', form=form)
