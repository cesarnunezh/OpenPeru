from flask import Blueprint, render_template
from flask_babel import gettext as _

landing_bp = Blueprint("landing", __name__, template_folder="../templates")


@landing_bp.route("/")
def index():
    """
    Landing page (main menu)
    """
    menu_items = [
        {"name": _("Bills"), "url": "/bills"},
        {"name": _("Congressmen"), "url": "/congress"},
    ]

    return render_template("landing/index.html", menu_items=menu_items)
