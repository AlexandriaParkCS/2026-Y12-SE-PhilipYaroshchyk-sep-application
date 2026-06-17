import functools

from flask import Blueprint
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash

from .db import get_db
from . import auth

bp = Blueprint("home", __name__, url_prefix="")

@bp.route("/", methods=("GET", "POST"))
@auth.login_required
def index():
    return render_template("index.html")


@bp.route("/about", methods=("GET", "POST"))
def about():
    return render_template("about.html")
    