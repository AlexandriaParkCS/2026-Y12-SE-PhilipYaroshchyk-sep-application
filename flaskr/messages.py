import logging

from flask import Blueprint
from flask import abort
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from .db import get_db
from . import auth

bp = Blueprint("messages", __name__, url_prefix="/messages")

log = logging.getLogger(__name__)


@bp.route("/")
@auth.login_required
def inbox():
    db = get_db()
    threads = db.execute(
        "SELECT users.id AS other_id, users.username AS other_name, "
        "MAX(messages.created_at) AS last_at, "
        "(SELECT body FROM messages AS m2 "
        " WHERE (m2.sender_id = users.id AND m2.recipient_id = ?) "
        "    OR (m2.sender_id = ? AND m2.recipient_id = users.id) "
        " ORDER BY m2.created_at DESC LIMIT 1) AS last_body "
        "FROM messages "
        "JOIN users ON users.id = CASE WHEN messages.sender_id = ? "
        "                              THEN messages.recipient_id ELSE messages.sender_id END "
        "WHERE messages.sender_id = ? OR messages.recipient_id = ? "
        "GROUP BY users.id "
        "ORDER BY last_at DESC;",
        (g.user["id"], g.user["id"], g.user["id"], g.user["id"], g.user["id"]),
    ).fetchall()
    return render_template("messages/inbox.html", threads=threads)


@bp.route("/<int:user_id>", methods=("GET", "POST"))
@auth.login_required
def thread(user_id):
    db = get_db()
    other_user = db.execute(
        "SELECT * FROM users WHERE id = ?;", (user_id,)
    ).fetchone()

    if other_user is None or user_id == g.user["id"]:
        abort(404)

    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if not body:
            flash("Message cannot be empty.", "error")
        else:
            db.execute(
                "INSERT INTO messages (sender_id, recipient_id, body) VALUES (?, ?, ?);",
                (g.user["id"], user_id, body),
            )
            db.commit()
        return redirect(url_for("messages.thread", user_id=user_id))

    thread_messages = db.execute(
        "SELECT * FROM messages "
        "WHERE (sender_id = ? AND recipient_id = ?) OR (sender_id = ? AND recipient_id = ?) "
        "ORDER BY created_at;",
        (g.user["id"], user_id, user_id, g.user["id"]),
    ).fetchall()

    return render_template(
        "messages/thread.html", other_user=other_user, messages=thread_messages
    )
