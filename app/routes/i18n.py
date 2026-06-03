from flask import Blueprint, session, redirect, request, url_for

i18n_bp = Blueprint("i18n", __name__)


@i18n_bp.route("/lang/<lang>")
def set_lang(lang):
    session["lang"] = lang
    return redirect(request.referrer or url_for("landing.index"))
