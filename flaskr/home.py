import functools
import logging
import os
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
    is_sitter = request.form.get("user_type") == "sitter"

    db = get_db()
    error = None

    if not email:
        error = "Email is required."

    if error is None:
        try:
            db.execute(
                "UPDATE users SET email = ?, postcode = ?, about = ?, is_sitter = ? WHERE id = ?",
                (email, postcode, about, is_sitter, g.user["id"]),
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

    log.info(f"Fetched details for pet ID {pet_id}: {g.pet['name']} with {len(g.care_types)} care types.")

    return render_template("pet_detail.html", pet=g.pet, care_types=g.care_types)


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
