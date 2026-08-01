import logging

from flask import Blueprint
from flask import current_app
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from .db import get_db
from .models import Booking
from .models import BookingRequest
from .models import CareType
from .models import Pet
from .models import Review
from . import auth

bp = Blueprint("home", __name__, url_prefix="")

log = logging.getLogger(__name__)


@bp.route("/", methods=("GET", "POST"))
@auth.login_required
def index():
    try:
        g.pets = Pet.get_all_for_owner(g.user.id)
        log.info(f"Fetched {len(g.pets)} pets for user {g.user.username} (ID: {g.user.id})")
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

    if not email:
        flash("Email is required.", "error")
        return redirect(url_for("home.index"))

    try:
        g.user.update_profile(email, postcode, about)
        flash("Profile updated successfully!", "success")
    except Exception as e:
        flash(f"Error updating profile: {e}", "error")

    return redirect(url_for("home.index"))


@bp.route("/upload_photo", methods=("POST",))
@auth.login_required
def upload_photo():
    photo_file = request.files.get("photo")

    try:
        error = g.user.upload_photo(photo_file, current_app.config["UPLOAD_FOLDER"])
        if error is None:
            flash("Photo updated successfully!", "success")
        else:
            flash(error, "error")
    except Exception as e:
        flash(f"Error updating photo: {e}", "error")

    return redirect(url_for("home.index"))


@bp.route("/apply_for_booking", methods=("POST",))
@auth.login_required
def apply_for_booking():
    if not g.user.is_profile_complete():
        flash("Please complete your profile (photo, postcode, and about) before applying for bookings.", "error")
        return redirect(url_for("home.index"))

    booking_id = request.form["booking_id"]
    booking = Booking.get_open(booking_id)

    if booking is None:
        flash("Booking not found or already confirmed.", "error")
        return redirect(url_for("home.index"))

    try:
        booking.request_sitter(g.user)
        flash("Application submitted!", "success")
    except Exception as e:
        flash(f"Error submitting application: {e}", "error")

    return redirect(url_for("home.index"))


@bp.route("/confirm_booking", methods=("POST",))
@auth.login_required
def confirm_booking():
    request_id = request.form["request_id"]
    booking_request = BookingRequest.get_for_owner(request_id, g.user.id)

    if booking_request is None:
        flash("Request not found or you do not have permission to confirm it.", "error")
        return redirect(url_for("home.index"))

    try:
        booking_request.accept()
        flash("Booking confirmed!", "success")
    except Exception as e:
        flash(f"Error confirming booking: {e}", "error")

    return redirect(url_for("home.pet_details", pet_id=booking_request.pet_id))


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
        (g.user.id, g.user.id),
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
        (booking_id, g.user.id, g.user.id),
    ).fetchone()

    if booking is None:
        flash("Booking not found or not eligible for review.", "error")
        return redirect(url_for("home.index"))

    try:
        review = Review(
            booking_id=booking_id,
            reviewer_id=g.user.id,
            reviewee_id=reviewee_id,
            score=int(score),
            comment=comment,
        )
        review.submit()
        flash("Review submitted!", "success")
    except Exception as e:
        flash(f"Error submitting review: {e}", "error")

    if booking["owner_id"] == g.user.id:
        return redirect(url_for("home.pet_details", pet_id=booking["pet_id"]))
    return redirect(url_for("home.sittings"))


@bp.route("/about", methods=("GET", "POST"))
def about():
    return render_template("about.html")

@bp.route("/privacy_policy", methods=("GET", "POST"))
def privacy_policy():
    return render_template("privacy_policy.html")

@bp.route("/add_pet", methods=("POST",))
@auth.login_required
def add_pet():
    name = request.form["name"]
    species = request.form["species"]
    breed = request.form["breed"]
    yob = request.form["yob"]

    log.info(f"Attempting to add pet: Name={name}, Species={species}, Breed={breed}, Year of Birth={yob}, Owner ID={g.user.id}")

    try:
        pet, error = Pet.create(g.user.id, name, species, breed, yob)
    except Exception as e:
        flash(f"Error adding pet to the database: {e}", "error")
        return redirect(url_for("home.index"))

    if error is None:
        flash(f"Pet {name} added successfully!", "success")
    else:
        flash(error, "error")

    return redirect(url_for("home.index"))


@bp.route("/pet_details/<int:pet_id>", methods=("GET",))
@auth.login_required
def pet_details(pet_id):
    g.pet = Pet.get_by_id_and_owner(pet_id, g.user.id)

    if g.pet is None:
        flash("Pet not found or you do not have permission to view this pet.", "error")
        return redirect(url_for("home.index"))

    details = g.pet.get_details(g.user.id)
    g.care_types = details["care_types"]
    g.bookings = details["bookings"]
    g.booking_requests = details["booking_requests"]

    log.info(f"Fetched details for pet ID {pet_id}: {g.pet.name} with {len(g.care_types)} care types.")

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
    start_date = request.form["start_date"]
    end_date = request.form["end_date"]
    daily_price = request.form["daily_price"]

    pet = Pet.get_by_id_and_owner(pet_id, g.user.id)

    if pet is None:
        flash("Pet not found or you do not have permission to book for it.", "error")
        return redirect(url_for("home.index"))

    try:
        booking, error = Booking.create(pet, start_date, end_date, daily_price)
    except Exception as e:
        flash(f"Error adding booking to the database: {e}", "error")
        return redirect(url_for("home.pet_details", pet_id=pet_id))

    if error is None:
        flash("Booking added successfully!", "success")
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

    try:
        _, warnings = CareType.create(pet_id, care_name, description, schedule)
        for warning in warnings:
            flash(warning, "error")
        flash(f"Care details for pet ID {pet_id} added successfully!", "success")
    except Exception as e:
        flash(f"Error adding care details to the database: {e}", "error")

    return redirect(url_for("home.pet_details", pet_id=pet_id))
