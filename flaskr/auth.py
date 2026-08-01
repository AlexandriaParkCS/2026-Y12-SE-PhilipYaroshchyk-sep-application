import functools

from flask import Blueprint
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from .models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = User.get_by_id(user_id)

@bp.route("/register", methods=("GET", "POST"))
def register():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        email = request.form["email"]

        user, error = User.register(username, email, password)

        if error is None:
            # Success, go to the login page.
            return redirect(url_for("auth.login"))

        flash(error)

    return render_template("auth/register.html")

@bp.route("/logout")
def logout():
    if g.user is not None:
        g.user.logout()
    else:
        session.clear()
    return redirect(url_for("home.index"))

@bp.route("/login", methods=("GET", "POST"))
def login():

    if request.method == "POST":

        password = request.form["password"]
        username = request.form["username"]

        user, error = User.authenticate(username, password)

        if error is None:
            user.login()
            g.user = user
            return redirect(url_for("home.index"))

        flash(error)

    return render_template("auth/login.html")

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrapped_view    
