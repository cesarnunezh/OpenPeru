from flask import Flask, request, session
from flask_babel import Babel
from app.routes.landing import landing_bp
from app.routes.bills import bills_bp
from app.routes.congress import congress_bp
from app.routes.i18n import i18n_bp
# from app.routes import landing_bp, bills_bp, congress_bp, info_bp

babel = Babel()


def get_locale():
    lang = session.get("lang")
    if not lang:
        lang = request.args.get("lang")
    if lang:
        return lang
    return request.accept_languages.best_match(["en", "es"]) or "en"


def create_app():
    app = Flask(__name__)

    app.register_blueprint(landing_bp)
    app.register_blueprint(bills_bp)
    app.register_blueprint(congress_bp)
    app.register_blueprint(i18n_bp)

    app.secret_key = "secret"

    app.config["BABEL_DEFAULT_LOCALE"] = "en"
    babel.init_app(app, locale_selector=get_locale)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
