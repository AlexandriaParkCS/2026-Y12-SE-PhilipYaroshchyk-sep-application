import logging
from flask import Blueprint
from flask import g
from flask import render_template
from flask import request

from .db import get_db
from . import auth

bp = Blueprint("search", __name__, url_prefix="/search")

log = logging.getLogger(__name__)


@bp.route("/sitters")
@auth.login_required
def sitters():
    query = request.args.get("q", "").strip()
    results = []

    if query:
        like = f"%{query}%"
        db = get_db()
        results = db.execute(
            "SELECT users.id, users.username, users.postcode, users.about, users.photo, "
            "ROUND(AVG(reviews.score), 1) AS avg_score, COUNT(reviews.id) AS review_count "
            "FROM users "
            "LEFT JOIN reviews ON reviews.reviewee_id = users.id "
            "WHERE users.id != ? "
            "AND (users.username LIKE ? OR users.postcode LIKE ? OR users.about LIKE ?) "
            "GROUP BY users.id;",
            (g.user["id"], like, like, like),
        ).fetchall()
        log.info(f"Sitter search for '{query}' returned {len(results)} results.")

    return render_template("search/sitters.html", query=query, results=results)


@bp.route("/pets")
@auth.login_required
def pets():
    query = request.args.get("q", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    results = []

    if query:
        like = f"%{query}%"
        sql = (
            "SELECT pets.id, pets.name, pets.species, pets.breed, pets.yob, "
            "users.username AS owner_name, "
            "bookings.id AS booking_id, bookings.daily_price, bookings.start_date, bookings.end_date "
            "FROM pets "
            "JOIN users ON users.id = pets.owner_id "
            "JOIN bookings ON bookings.pet_id = pets.id "
            "WHERE pets.owner_id != ? "
            "AND bookings.sitter_id IS NULL "
            "AND (pets.name LIKE ? OR pets.species LIKE ? OR pets.breed LIKE ?)"
        )
        params = [g.user["id"], like, like, like]

        if min_price:
            sql += " AND bookings.daily_price >= ?"
            params.append(int(min_price))
        if max_price:
            sql += " AND bookings.daily_price <= ?"
            params.append(int(max_price))

        db = get_db()
        results = db.execute(sql, params).fetchall()
        log.info(f"Pet search for '{query}' returned {len(results)} results.")

    profile_complete = bool(g.user["about"] and g.user["postcode"] and g.user["photo"])
    return render_template("search/pets.html", query=query, min_price=min_price, max_price=max_price, results=results, profile_complete=profile_complete)
