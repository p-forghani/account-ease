import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from config import DevelopmentConfig, ProductionConfig

db = SQLAlchemy()
login = LoginManager()
login.login_view = 'auth.login'  # type: ignore
migrate = Migrate()

def create_app(
    config_class=DevelopmentConfig
    if os.getenv('FLASK_ENV') == 'development'
    else ProductionConfig
):
    app = Flask(__name__, static_folder='static')
    app.config.from_object(config_class)

    # Disable Flask's default logging to avoid duplicates
    app.logger.handlers.clear()

    # Configure logging
    # Always set up console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter(app.config['LOG_FORMAT'])
    )
    console_handler.setLevel(
        getattr(logging, app.config['LOG_LEVEL'])
    )
    app.logger.addHandler(console_handler)

    # File handler for production and when not in debug mode
    if not app.debug and not app.testing:
        # File handler for production
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler(
            app.config['LOG_FILE'],
            maxBytes=10240000,
            backupCount=10
        )
        file_handler.setFormatter(
            logging.Formatter(app.config['LOG_FORMAT'])
        )
        file_handler.setLevel(
            getattr(logging, app.config['LOG_LEVEL'])
        )
        app.logger.addHandler(file_handler)

    app.logger.setLevel(getattr(logging, app.config['LOG_LEVEL']))
    app.logger.info('ClientEase startup')
    
    # Set up memory monitoring
    if app.config.get('ENABLE_MEMORY_MONITORING', False):
        from app.utils.memory_monitor import setup_memory_monitoring_middleware, MemoryMonitor
        setup_memory_monitoring_middleware(app)
        
        # Log initial memory usage
        monitor = MemoryMonitor(app.logger)
        monitor.log_memory_usage('App Startup')
        app.logger.info('Memory monitoring enabled')

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    
    # Register CLI commands (import here to avoid circular imports)
    from app.commands import seed_db, memory_check
    app.cli.add_command(seed_db)
    app.cli.add_command(memory_check)

    # Test database connection at startup
    with app.app_context():
        try:
            # Try to execute a simple query to test connection
            with db.engine.connect() as connection:
                connection.execute(db.text('SELECT 1'))
            app.logger.info('Database connection successful')
        except Exception as e:
            app.logger.error(f'Database connection failed: {e}')
            raise RuntimeError(
                f"Failed to connect to PostgreSQL database: {e}. "
                "Please check your DATABASE_URL configuration."
            ) from e

    from app.admin import bp as admin_bp
    from app.auth import bp as auth_bp
    from app.client import bp as client_bp
    from app.invoice import bp as invoice_bp
    from app.main import bp as main_bp
    from app.project import bp as prj_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(prj_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(invoice_bp)

    # Register error handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    # Import models to register them with SQLAlchemy
    from app import models  # noqa

    return app
