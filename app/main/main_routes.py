from flask import current_app, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta, timezone
import sqlalchemy as sa

from app.main import bp
from app import db
from app.models import Client, Project, Invoice
from app.models.project_models import InvoiceStatus
from app.utils.memory_monitor import monitor_memory_usage


@bp.route('/')
@monitor_memory_usage("Index Load")
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    current_app.logger.info('Index route called')
    return render_template('index.html')

@bp.route('/dashboard')
@login_required
@monitor_memory_usage("Dashboard Load")
def dashboard():
    current_app.logger.info('Dashboard route called')
    
    # Get current date and calculate date ranges
    now = datetime.now(tz=timezone.utc)
    week_from_now = now + timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # Clients Summary
    total_clients = db.session.scalar(
        sa.select(sa.func.count(Client.id))
        .where(Client.user_id == current_user.id)
    )
    
    new_clients_this_month = db.session.scalar(
        sa.select(sa.func.count(Client.id))
        .where(
            sa.and_(
                Client.user_id == current_user.id,
                Client.created_at >= month_ago
            )
        )
    )
    
    # Projects Summary
    total_projects = db.session.scalar(
        sa.select(sa.func.count(Project.id))
        .where(Project.user_id == current_user.id)
    )
    
    active_projects = db.session.scalar(
        sa.select(sa.func.count(Project.id))
        .where(
            sa.and_(
                Project.user_id == current_user.id,
                Project.end_date.is_(None)  # No end date means active
            )
        )
    )
    
    projects_ending_soon = db.session.scalar(
        sa.select(sa.func.count(Project.id))
        .where(
            sa.and_(
                Project.user_id == current_user.id,
                Project.end_date.isnot(None),
                Project.end_date <= week_from_now,
                Project.end_date >= now
            )
        )
    )
    
    # Invoices Summary
    total_invoices = db.session.scalar(
        sa.select(sa.func.count(Invoice.id))
        .where(Invoice.user_id == current_user.id)
    )
    
    pending_invoices = db.session.scalar(
        sa.select(sa.func.count(Invoice.id))
        .where(
            sa.and_(
                Invoice.user_id == current_user.id,
                Invoice.status == InvoiceStatus.PENDING
            )
        )
    )
    
    overdue_invoices = db.session.scalar(
        sa.select(sa.func.count(Invoice.id))
        .where(
            sa.and_(
                Invoice.user_id == current_user.id,
                Invoice.status == InvoiceStatus.OVERDUE
            )
        )
    )
    
    # Calculate total pending amount
    total_pending_amount = db.session.scalar(
        sa.select(sa.func.sum(Invoice.amount))
        .where(
            sa.and_(
                Invoice.user_id == current_user.id,
                Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE])
            )
        )
    ) or 0
    
    # Get recent projects (last 5)
    recent_projects = db.session.scalars(
        sa.select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(Project.start_date.desc())
        .limit(5)
    ).all()
    
    # Get upcoming deadlines (invoices due this week)
    upcoming_invoices = db.session.scalars(
        sa.select(Invoice)
        .where(
            sa.and_(
                Invoice.user_id == current_user.id,
                Invoice.status == InvoiceStatus.PENDING,
                Invoice.date <= week_from_now,
                Invoice.date >= now
            )
        )
        .order_by(Invoice.date.asc())
        .limit(5)
    ).all()
    
    dashboard_data = {
        'clients': {
            'total': total_clients,
            'new_this_month': new_clients_this_month,
        },
        'projects': {
            'total': total_projects,
            'active': active_projects,
            'ending_soon': projects_ending_soon,
        },
        'invoices': {
            'total': total_invoices,
            'pending': pending_invoices,
            'overdue': overdue_invoices,
            'pending_amount': total_pending_amount,
        },
        'recent_projects': recent_projects,
        'upcoming_invoices': upcoming_invoices,
    }
    
    return render_template('dashboard.html', dashboard_data=dashboard_data)

