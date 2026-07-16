import functools
import logging
import os
from datetime import date
from flask import Blueprint
from flask import current_app
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from .db import get_db
from . import auth

bp = Blueprint("home", __name__, url_prefix="")

log = logging.getLogger(__name__)

ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_photo(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS

@bp.route("/", methods=("GET", "POST"))
@auth.login_required
def index():
    db = get_db()

    try:
        g.pets = db.execute(
            "SELECT * FROM pets WHERE owner_id = ?;", (g.user["id"],)
        ).fetchall()

        log.info(f"Fetched {len(g.pets)} pets for user {g.user['username']} (ID: {g.user['id']})")

    except Exception as e:
        flash(f"Error fetching data from the database: {e}", "error")
        return render_template("index.html")

    return render_template("index.html")


@bp.route("/update_profile", methods=("POST",))
@auth.login_required
def update_profile():
    email = request.form["email"]
    postcode = request.form.get("postcode") or None
    about = request.form.get("about", "")

    db = get_db()
    error = None

    if not email:
        error = "Email is required."

    if error is None:
        try:
            db.execute(
                "UPDATE users SET email = ?, postcode = ?, about = ? WHERE id = ?",
                (email, postcode, about, g.user["id"]),
            )
            db.commit()
            flash("Profile updated successfully!", "success")
        except Exception as e:
            flash(f"Error updating profile: {e}", "error")
    else:
        flash(error, "error")

    return redirect(url_for("home.index"))


@bp.route("/upload_photo", methods=("POST",))
@auth.login_required
def upload_photo():
    photo_file = request.files.get("photo")

    if not photo_file or not photo_file.filename:
        flash("Please choose a photo to upload.", "error")
        return redirect(url_for("home.index"))

    if not allowed_photo(photo_file.filename):
        flash("Photo must be a png, jpg, jpeg, or gif file.", "error")
        return redirect(url_for("home.index"))

    filename = secure_filename(f"user_{g.user['id']}_{photo_file.filename}")
    photo_file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
    photo = url_for("static", filename=f"uploads/{filename}")

    db = get_db()
    try:
        db.execute("UPDATE users SET photo = ? WHERE id = ?", (photo, g.user["id"]))
        db.commit()
        flash("Photo updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating photo: {e}", "error")

    return redirect(url_for("home.index"))


@bp.route("/apply_for_booking", methods=("POST",))
@auth.login_required
def apply_for_booking():
    if not g.user["about"] or not g.user["postcode"] or not g.user["photo"]:
        flash("Please complete your profile (photo, postcode, and about) before applying for bookings.", "error")
        return redirect(url_for("home.index"))

    booking_id = request.form["booking_id"]
    db = get_db()

    booking = db.execute(
        "SELECT * FROM bookings WHERE id = ? AND sitter_id IS NULL;", (booking_id,)
    ).fetchone()

    if booking is None:
        flash("Booking not found or already confirmed.", "error")
        return redirect(url_for("home.index"))

    try:
        db.execute(
            "INSERT INTO booking_requests (booking_id, sitter_id) VALUES (?, ?);",
            (booking_id, g.user["id"]),
        )
        db.commit()
        flash("Application submitted!", "success")
    except Exception as e:
        flash(f"Error submitting application: {e}", "error")

    return redirect(url_for("home.index"))


@bp.route("/confirm_booking", methods=("POST",))
@auth.login_required
def confirm_booking():
    request_id = request.form["request_id"]
    db = get_db()

    booking_request = db.execute(
        "SELECT booking_requests.*, bookings.pet_id FROM booking_requests "
        "JOIN bookings ON bookings.id = booking_requests.booking_id "
        "JOIN pets ON pets.id = bookings.pet_id "
        "WHERE booking_requests.id = ? AND pets.owner_id = ?;",
        (request_id, g.user["id"]),
    ).fetchone()

    if booking_request is None:
        flash("Request not found or you do not have permission to confirm it.", "error")
        return redirect(url_for("home.index"))

    try:
        db.execute(
            "UPDATE bookings SET sitter_id = ? WHERE id = ?;",
            (booking_request["sitter_id"], booking_request["booking_id"]),
        )
        db.commit()
        flash("Booking confirmed!", "success")
    except Exception as e:
        flash(f"Error confirming booking: {e}", "error")

    return redirect(url_for("home.pet_details", pet_id=booking_request["pet_id"]))


@bp.route("/sittings")
@auth.login_required
def sittings():
    db = get_db()
    bookings = db.execute(
        "SELECT bookings.*, pets.name AS pet_name, pets.species, pets.breed, "
        "users.id AS owner_id, users.username AS owner_name, "
        "reviews.id AS review_id "
        "FROM bookings "
        "JOIN pets ON pets.id = bookings.pet_id "
        "JOIN users ON users.id = pets.owner_id "
        "LEFT JOIN reviews ON reviews.booking_id = bookings.id AND reviews.reviewer_id = ? "
        "WHERE bookings.sitter_id = ? "
        "ORDER BY bookings.start_date;",
        (g.user["id"], g.user["id"]),
    ).fetchall()
    return render_template("sittings.html", bookings=bookings)


@bp.route("/add_review", methods=("POST",))
@auth.login_required
def add_review():
    booking_id = request.form["booking_id"]
    reviewee_id = request.form["reviewee_id"]
    score = request.form["score"]
    comment = request.form.get("comment", "")

    db = get_db()

    booking = db.execute(
        "SELECT bookings.*, pets.owner_id FROM bookings "
        "JOIN pets ON pets.id = bookings.pet_id "
        "WHERE bookings.id = ? AND bookings.sitter_id IS NOT NULL "
        "AND (pets.owner_id = ? OR bookings.sitter_id = ?);",
        (booking_id, g.user["id"], g.user["id"]),
    ).fetchone()

    if booking is None:
        flash("Booking not found or not eligible for review.", "error")
        return redirect(url_for("home.index"))

    try:
        db.execute(
            "INSERT INTO reviews (booking_id, reviewer_id, reviewee_id, score, comment) VALUES (?, ?, ?, ?, ?);",
            (booking_id, g.user["id"], reviewee_id, int(score), comment),
        )
        db.commit()
        flash("Review submitted!", "success")
    except Exception as e:
        flash(f"Error submitting review: {e}", "error")

    if booking["owner_id"] == g.user["id"]:
        return redirect(url_for("home.pet_details", pet_id=booking["pet_id"]))
    return redirect(url_for("home.sittings"))


@bp.route("/about", methods=("GET", "POST"))
def about():
    return render_template("about.html")


@bp.route("/add_pet", methods=("POST",))
@auth.login_required
def add_pet():

    name = request.form["name"]
    species = request.form["species"]
    breed = request.form["breed"]
    yob = request.form["yob"]
    db = get_db()
    error = None

    log.info(f"Attempting to add pet: Name={name}, Species={species}, Breed={breed}, Year of Birth={yob}, Owner ID={g.user['id']}")

    if not name:
        error = "Name is required."
    elif not species:
        error = "Species is required."
    elif not breed:
        error = "Breed is required."
    elif not yob:
        error = "Year of Birth is required."

    if error is None:
        try:
            db.execute(
                "INSERT INTO pets (name, species, breed, yob, owner_id) VALUES (?, ?, ?, ?, ?)",
                (name, species, breed, yob, g.user["id"]),
            )
            db.commit()
            flash(f"Pet {name} added successfully!", "success")
        except Exception as e:
            flash(f"Error adding pet to the database: {e}", "error")
    else:
        flash(error, "error")

    return redirect(url_for("home.index"))


@bp.route("/pet_details/<int:pet_id>", methods=("GET",))
@auth.login_required
def pet_details(pet_id):
    db = get_db()
    g.pet = db.execute(
        "SELECT * FROM pets WHERE id = ? AND owner_id = ?;", (pet_id, g.user["id"])
    ).fetchone()

  
    if g.pet is None:
        flash("Pet not found or you do not have permission to view this pet.", "error")
        return redirect(url_for("home.index"))
    
    g.care_types = db.execute(
        "SELECT * FROM care_types WHERE pet_id = ?;", (pet_id,)
    ).fetchall()

    g.bookings = db.execute(
        "SELECT bookings.*, users.username AS sitter_name, "
        "reviews.id AS review_id "
        "FROM bookings "
        "LEFT JOIN users ON users.id = bookings.sitter_id "
        "LEFT JOIN reviews ON reviews.booking_id = bookings.id AND reviews.reviewer_id = ? "
        "WHERE bookings.pet_id = ?;",
        (g.user["id"], pet_id),
    ).fetchall()

    g.booking_requests = db.execute(
        "SELECT booking_requests.id AS request_id, booking_requests.booking_id, "
        "users.id AS sitter_id, users.username AS sitter_name, "
        "users.postcode, users.about, users.photo, "
        "ROUND(AVG(reviews.score), 1) AS avg_score, COUNT(reviews.id) AS review_count "
        "FROM booking_requests "
        "JOIN bookings ON bookings.id = booking_requests.booking_id "
        "JOIN users ON users.id = booking_requests.sitter_id "
        "LEFT JOIN reviews ON reviews.reviewee_id = users.id "
        "WHERE bookings.pet_id = ? AND bookings.sitter_id IS NULL "
        "GROUP BY booking_requests.id;",
        (pet_id,),
    ).fetchall()

    log.info(f"Fetched details for pet ID {pet_id}: {g.pet['name']} with {len(g.care_types)} care types.")

    return render_template(
        "pet_detail.html",
        pet=g.pet,
        care_types=g.care_types,
        bookings=g.bookings,
        booking_requests=g.booking_requests,
    )


@bp.route("/add_booking", methods=("POST",))
@auth.login_required
def add_booking():
    pet_id = request.form["pet_id"]
    sitter_id = None
    start_date = request.form["start_date"]
    end_date = request.form["end_date"]
    daily_price = request.form["daily_price"]

    db = get_db()
    error = None

    pet = db.execute(
        "SELECT * FROM pets WHERE id = ? AND owner_id = ?;", (pet_id, g.user["id"])
    ).fetchone()

    if pet is None:
        flash("Pet not found or you do not have permission to book for it.", "error")
        return redirect(url_for("home.index"))

    if not start_date:
        error = "Start date is required."
    elif not end_date:
        error = "End date is required."
    elif not daily_price:
        error = "Daily price is required."
    else:
        try:
            parsed_start = date.fromisoformat(start_date)
            parsed_end = date.fromisoformat(end_date)
            if parsed_start < date.today():
                error = "Start date cannot be in the past."
            elif parsed_end < date.today():
                error = "End date cannot be in the past."
            elif parsed_end < parsed_start:
                error = "End date must be after start date."
        except ValueError:
            error = "Dates must be valid."

    if error is None:
        try:
            daily_price = round(float(daily_price))
        except ValueError:
            error = "Daily price must be a number."

    if error is None:
        try:
            db.execute(
                "INSERT INTO bookings (pet_id, sitter_id, start_date, end_date, daily_price) VALUES (?, ?, ?, ?, ?)",
                (pet_id, sitter_id, start_date, end_date, daily_price),
            )
            db.commit()
            flash("Booking added successfully!", "success")
        except Exception as e:
            flash(f"Error adding booking to the database: {e}", "error")
    else:
        flash(error, "error")

    return redirect(url_for("home.pet_details", pet_id=pet_id))


@bp.route("/add_care_details", methods=("POST",))
@auth.login_required
def add_care_details():

    pet_id = request.form["pet_id"]
    description = request.form["description"]
    schedule = request.form["schedule"]
    care_name = request.form["name"]

    if not care_name:
        flash("Care type name is required.", "error")
    if not description:
        flash("Description is required.", "error")
    if not schedule:
        flash("Schedule is required.", "error")
    if not pet_id:
        flash("Pet ID is required.", "error")

    db = get_db()
    try:
        db.execute(
            "INSERT INTO care_types (pet_id, name, description, schedule) VALUES (?, ?, ?, ?)",
            (pet_id, care_name, description, schedule),
        )
        db.commit()
        flash(f"Care details for pet ID {pet_id} added successfully!", "success")
    except Exception as e:
        flash(f"Error adding care details to the database: {e}", "error")   


    return redirect(url_for("home.pet_details", pet_id=pet_id))    
