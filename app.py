"""
StockRoom - Inventory Management System
Entry point.

Run with:  python app.py
Then open: http://127.0.0.1:5000

The application is built with the factory pattern (create_app) rather
than a single global `app` object. Each feature area lives in its own
blueprint under blueprints/, so products code never sits in the same
file as supplier code.
"""

from flask import Flask, render_template, session
from datetime import datetime

import db
from config import Config

from blueprints.auth import auth_bp
from blueprints.dashboard import dashboard_bp
from blueprints.products import products_bp
from blueprints.categories import categories_bp
from blueprints.suppliers import suppliers_bp
from blueprints.movements import movements_bp
from blueprints.users import users_bp
from blueprints.reports import reports_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register the teardown handler that closes MySQL connections.
    db.init_app(app)

    # Each blueprint owns one feature area and its own URL prefix.
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp, url_prefix="/products")
    app.register_blueprint(categories_bp, url_prefix="/categories")
    app.register_blueprint(suppliers_bp, url_prefix="/suppliers")
    app.register_blueprint(movements_bp, url_prefix="/movements")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(reports_bp, url_prefix="/reports")

    # --- Template helpers ------------------------------------------
    @app.context_processor
    def inject_globals():
        """Values every template can use without being passed them."""
        return {
            "current_user": {
                "id": session.get("user_id"),
                "name": session.get("full_name"),
                "role": session.get("role"),
            },
            "currency": app.config["CURRENCY"],
            "now": datetime.now(),
        }

    @app.template_filter("money")
    def money(value):
        """Format a number as 185,000.00 - readable in a stock report."""
        try:
            return f"{float(value):,.2f}"
        except (TypeError, ValueError):
            return "0.00"

    @app.template_filter("datetimeformat")
    def datetimeformat(value, fmt="%d %b %Y, %H:%M"):
        if value is None:
            return "-"
        return value.strftime(fmt)

    # --- Error pages -----------------------------------------------
    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html",
                               code=404,
                               message="That page does not exist."), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("error.html",
                               code=500,
                               message="Something went wrong on the server."), 500

    return app


if __name__ == "__main__":
    application = create_app()
    # debug=True gives auto-reload and a traceback in the browser while
    # you are building. Set it to False before recording your demo.
    application.run(debug=True, host="127.0.0.1", port=5000)
