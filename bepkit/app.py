"""Application factory."""

from __future__ import annotations

from flask import Flask, jsonify

from .config import load_config
from .extensions import db


def create_app(testing: bool = False) -> Flask:
    app = Flask(
        __name__,
        template_folder="web/templates",
        static_folder="web/static",
        static_url_path="/static",
    )
    app.config.from_object(load_config(testing))

    db.init_app(app)

    from .web.api import api_bp
    from .web.views import web_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    _register_jinja(app)
    _register_errors(app)

    with app.app_context():
        db.create_all()

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok", app=app.config["APP_NAME"])

    return app


def _register_jinja(app: Flask) -> None:
    from .i18n import LOCALES, get_locale, translate
    from .web.filters import FILTERS, GLOBALS

    app.jinja_env.filters.update(FILTERS)
    app.jinja_env.globals.update(GLOBALS)
    app.jinja_env.globals["app_name"] = app.config["APP_NAME"]
    # Resolved per request, so a template can switch language without a restart.
    app.jinja_env.globals["t"] = translate
    app.jinja_env.globals["locale"] = get_locale
    app.jinja_env.globals["locales"] = LOCALES


def _register_errors(app: Flask) -> None:
    from flask import render_template, request

    def wants_json() -> bool:
        return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"

    @app.errorhandler(404)
    def not_found(exc):
        if wants_json():
            return jsonify(error="not found"), 404
        return render_template("error.html", code=404,
                               message="That page does not exist."), 404

    @app.errorhandler(500)
    def server_error(exc):  # pragma: no cover - defensive
        db.session.rollback()
        if wants_json():
            return jsonify(error="internal server error"), 500
        return render_template("error.html", code=500,
                               message="Something went wrong on our side."), 500
