import click
from flask.cli import with_appcontext
from flask import current_app
from app import db
from app.models import Role
from app.utils.memory_monitor import MemoryMonitor

@click.command("seed-db")
@with_appcontext
def seed_db():
    """Seed the database with initial data."""
    roles = [
        {"id": 1, "name": "Admin", "description": "Admin role"},
        {"id": 2, "name": "User", "description": "User role"},
        {"id": 3, "name": "Customer", "description": "Customer role"}]

    for role in roles:
        if not Role.query.filter_by(name=role["name"]).first():
            db.session.add(
                Role(
                    id=role["id"],
                    name=role["name"],
                    description=role["description"]
                )
            )


    db.session.commit()
    click.echo("✅ Database roles seeded successfully!")


@click.command("memory-check")
@with_appcontext
def memory_check():
    """Check current memory usage."""
    monitor = MemoryMonitor(current_app.logger)
    memory_info = monitor.get_memory_info()
    
    if memory_info:
        process_info = memory_info['process']
        system_info = memory_info['system']
        
        click.echo("\n📊 Current Memory Usage:")
        click.echo(f"Process Memory: {process_info['rss_mb']}MB ({process_info['percent']}% of system)")
        click.echo(f"System Memory: {system_info['used_mb']}/{system_info['total_mb']}MB ({system_info['percent']}%)")
        click.echo(f"Available Memory: {system_info['available_mb']}MB")
    else:
        click.echo("❌ Failed to get memory information")
