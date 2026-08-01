"""Domain classes implementing the AD-07 class diagram.

Each class wraps the corresponding SQLite table and exposes real
attributes plus the behaviour named in the diagram. ``__getitem__`` is
implemented so existing Jinja templates (which use ``obj['field']``
access, matching the old sqlite3.Row rows) keep working unchanged.

Multi-table joins built purely for display (search results, sittings
listings, message threads, etc.) are intentionally left as raw
``sqlite3.Row`` query results in the blueprints — they are report rows,
not single domain entities, so wrapping them here would misrepresent
the design.
"""

import os
from datetime import date

from flask import session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from .db import get_db

ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


class User:
    def __init__(self, id, username, email, postcode, photo, about, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.postcode = postcode
        self.photo = photo
        self.about = about
        self._password_hash = password_hash

    def __getitem__(self, key):
        return getattr(self, key)

    @classmethod
    def _from_row(cls, row):
        if row is None:
            return None
        return cls(
            row["id"], row["username"], row["email"], row["postcode"],
            row["photo"], row["about"], row["password_hash"],
        )

    @classmethod
    def get_by_id(cls, user_id):
        row = get_db().execute("SELECT * FROM users WHERE id = ?;", (user_id,)).fetchone()
        return cls._from_row(row)

    @classmethod
    def get_by_username(cls, username):
        row = get_db().execute("SELECT * FROM users WHERE username = ?;", (username,)).fetchone()
        return cls._from_row(row)

    @classmethod
    def register(cls, username, email, password):
        error = None
        if not username:
            error = "Username is required."
        elif not password:
            error = "Password is required."
        elif not email:
            error = "Email is required."

        if error is not None:
            return None, error

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?);",
                (username, email, generate_password_hash(password)),
            )
            db.commit()
        except db.IntegrityError:
            return None, f"User {username} is already registered."

        return cls.get_by_username(username), None

    @classmethod
    def authenticate(cls, username, password):
        user = cls.get_by_username(username)
        if user is None or not check_password_hash(user._password_hash, password):
            return None, "Incorrect credentials."
        return user, None

    def login(self):
        session.clear()
        session["user_id"] = self.id

    def logout(self):
        session.clear()

    def update_profile(self, email, postcode, about):
        db = get_db()
        db.execute(
            "UPDATE users SET email = ?, postcode = ?, about = ? WHERE id = ?;",
            (email, postcode, about, self.id),
        )
        db.commit()
        self.email, self.postcode, self.about = email, postcode, about

    def upload_photo(self, photo_file, upload_folder):
        if not photo_file or not photo_file.filename:
            return "Please choose a photo to upload."

        filename = photo_file.filename
        if "." not in filename or filename.rsplit(".", 1)[1].lower() not in ALLOWED_PHOTO_EXTENSIONS:
            return "Photo must be a png, jpg, jpeg, or gif file."

        saved_name = secure_filename(f"user_{self.id}_{filename}")
        photo_file.save(os.path.join(upload_folder, saved_name))
        photo = url_for("static", filename=f"uploads/{saved_name}")

        db = get_db()
        db.execute("UPDATE users SET photo = ? WHERE id = ?;", (photo, self.id))
        db.commit()
        self.photo = photo
        return None

    def is_profile_complete(self):
        return bool(self.about and self.postcode and self.photo)


class Pet:
    def __init__(self, id, name, species, breed, yob, owner_id):
        self.id = id
        self.name = name
        self.species = species
        self.breed = breed
        self.yob = yob
        self.owner_id = owner_id

    def __getitem__(self, key):
        return getattr(self, key)

    @classmethod
    def _from_row(cls, row):
        if row is None:
            return None
        return cls(row["id"], row["name"], row["species"], row["breed"], row["yob"], row["owner_id"])

    @classmethod
    def get_by_id_and_owner(cls, pet_id, owner_id):
        row = get_db().execute(
            "SELECT * FROM pets WHERE id = ? AND owner_id = ?;", (pet_id, owner_id)
        ).fetchone()
        return cls._from_row(row)

    @classmethod
    def get_all_for_owner(cls, owner_id):
        rows = get_db().execute(
            "SELECT * FROM pets WHERE owner_id = ?;", (owner_id,)
        ).fetchall()
        return [cls._from_row(row) for row in rows]

    @classmethod
    def create(cls, owner_id, name, species, breed, yob):
        error = None
        if not name:
            error = "Name is required."
        elif not species:
            error = "Species is required."
        elif not breed:
            error = "Breed is required."
        elif not yob:
            error = "Year of Birth is required."

        if error is not None:
            return None, error

        db = get_db()
        db.execute(
            "INSERT INTO pets (name, species, breed, yob, owner_id) VALUES (?, ?, ?, ?, ?);",
            (name, species, breed, yob, owner_id),
        )
        db.commit()
        return cls.get_all_for_owner(owner_id)[-1], None

    def add_care_type(self, name, description, schedule):
        return CareType.create(self.id, name, description, schedule)

    def get_details(self, current_user_id):
        db = get_db()

        care_type_rows = db.execute(
            "SELECT * FROM care_types WHERE pet_id = ?;", (self.id,)
        ).fetchall()
        care_types = [CareType._from_row(row) for row in care_type_rows]

        bookings = db.execute(
            "SELECT bookings.*, users.username AS sitter_name, "
            "reviews.id AS review_id "
            "FROM bookings "
            "LEFT JOIN users ON users.id = bookings.sitter_id "
            "LEFT JOIN reviews ON reviews.booking_id = bookings.id AND reviews.reviewer_id = ? "
            "WHERE bookings.pet_id = ?;",
            (current_user_id, self.id),
        ).fetchall()

        booking_requests = db.execute(
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
            (self.id,),
        ).fetchall()

        return {
            "care_types": care_types,
            "bookings": bookings,
            "booking_requests": booking_requests,
        }


class CareType:
    def __init__(self, id, pet_id, name, description, schedule):
        self.id = id
        self.pet_id = pet_id
        self.name = name
        self.description = description
        self.schedule = schedule

    def __getitem__(self, key):
        return getattr(self, key)

    @classmethod
    def _from_row(cls, row):
        if row is None:
            return None
        return cls(row["id"], row["pet_id"], row["name"], row["description"], row["schedule"])

    @classmethod
    def create(cls, pet_id, name, description, schedule):
        """Flags any missing field but, per the documented design (AD-04
        'Add Care Details'), inserts regardless of those warnings."""
        errors = []
        if not name:
            errors.append("Care type name is required.")
        if not description:
            errors.append("Description is required.")
        if not schedule:
            errors.append("Schedule is required.")
        if not pet_id:
            errors.append("Pet ID is required.")

        db = get_db()
        cur = db.execute(
            "INSERT INTO care_types (pet_id, name, description, schedule) VALUES (?, ?, ?, ?);",
            (pet_id, name, description, schedule),
        )
        db.commit()
        return cls(cur.lastrowid, pet_id, name, description, schedule), errors


class Booking:
    def __init__(self, id, pet_id, sitter_id, start_date, end_date, daily_price):
        self.id = id
        self.pet_id = pet_id
        self.sitter_id = sitter_id
        self.start_date = start_date
        self.end_date = end_date
        self.daily_price = daily_price

    def __getitem__(self, key):
        return getattr(self, key)

    @classmethod
    def _from_row(cls, row):
        if row is None:
            return None
        return cls(
            row["id"], row["pet_id"], row["sitter_id"],
            row["start_date"], row["end_date"], row["daily_price"],
        )

    @classmethod
    def get_open(cls, booking_id):
        row = get_db().execute(
            "SELECT * FROM bookings WHERE id = ? AND sitter_id IS NULL;", (booking_id,)
        ).fetchone()
        return cls._from_row(row)

    @classmethod
    def create(cls, pet, start_date, end_date, daily_price):
        error = None
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

        if error is not None:
            return None, error

        db = get_db()
        cur = db.execute(
            "INSERT INTO bookings (pet_id, sitter_id, start_date, end_date, daily_price) "
            "VALUES (?, ?, ?, ?, ?);",
            (pet.id, None, start_date, end_date, daily_price),
        )
        db.commit()
        return cls(cur.lastrowid, pet.id, None, start_date, end_date, daily_price), None

    def request_sitter(self, user):
        db = get_db()
        db.execute(
            "INSERT INTO booking_requests (booking_id, sitter_id) VALUES (?, ?);",
            (self.id, user.id),
        )
        db.commit()

    def confirm(self, sitter_id):
        db = get_db()
        db.execute(
            "UPDATE bookings SET sitter_id = ? WHERE id = ?;", (sitter_id, self.id)
        )
        db.commit()
        self.sitter_id = sitter_id


class BookingRequest:
    def __init__(self, id, booking_id, sitter_id, pet_id=None):
        self.id = id
        self.booking_id = booking_id
        self.sitter_id = sitter_id
        self.pet_id = pet_id

    def __getitem__(self, key):
        return getattr(self, key)

    @classmethod
    def get_for_owner(cls, request_id, owner_id):
        row = get_db().execute(
            "SELECT booking_requests.*, bookings.pet_id FROM booking_requests "
            "JOIN bookings ON bookings.id = booking_requests.booking_id "
            "JOIN pets ON pets.id = bookings.pet_id "
            "WHERE booking_requests.id = ? AND pets.owner_id = ?;",
            (request_id, owner_id),
        ).fetchone()
        if row is None:
            return None
        return cls(row["id"], row["booking_id"], row["sitter_id"], row["pet_id"])

    def accept(self):
        db = get_db()
        db.execute(
            "UPDATE bookings SET sitter_id = ? WHERE id = ?;",
            (self.sitter_id, self.booking_id),
        )
        db.commit()


class Review:
    def __init__(self, booking_id, reviewer_id, reviewee_id, score, comment, id=None):
        self.id = id
        self.booking_id = booking_id
        self.reviewer_id = reviewer_id
        self.reviewee_id = reviewee_id
        self.score = score
        self.comment = comment

    def __getitem__(self, key):
        return getattr(self, key)

    def submit(self):
        db = get_db()
        cur = db.execute(
            "INSERT INTO reviews (booking_id, reviewer_id, reviewee_id, score, comment) "
            "VALUES (?, ?, ?, ?, ?);",
            (self.booking_id, self.reviewer_id, self.reviewee_id, self.score, self.comment),
        )
        db.commit()
        self.id = cur.lastrowid
        return self.id


class Message:
    def __init__(self, sender_id, recipient_id, body, id=None, created_at=None):
        self.id = id
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.body = body
        self.created_at = created_at

    def __getitem__(self, key):
        return getattr(self, key)

    def send(self):
        db = get_db()
        cur = db.execute(
            "INSERT INTO messages (sender_id, recipient_id, body) VALUES (?, ?, ?);",
            (self.sender_id, self.recipient_id, self.body),
        )
        db.commit()
        self.id = cur.lastrowid
        return self.id
