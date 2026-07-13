CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    is_sitter BOOLEAN NOT NULL DEFAULT FALSE,
    postcode INTEGER,
    photo TEXT,
    about TEXT,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    species TEXT NOT NULL,
    breed TEXT,
    yob INTEGER,
    owner_id INTEGER NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS care_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    schedule TEXT NOT NULL,
    pet_id INTEGER NOT NULL,
    FOREIGN KEY (pet_id) REFERENCES pets (id)
);


CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL,
    sitter_id INTEGER,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    daily_price INTEGER NOT NULL,
    FOREIGN KEY (pet_id) REFERENCES pets (id),
    FOREIGN KEY (sitter_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    reviewer_id INTEGER NOT NULL,
    reviewee_id INTEGER NOT NULL,
    score INTEGER NOT NULL CHECK (score >= 1 AND score <= 5),
    comment TEXT,
    FOREIGN KEY (booking_id) REFERENCES bookings (id),
    FOREIGN KEY (reviewer_id) REFERENCES users (id),
    FOREIGN KEY (reviewee_id) REFERENCES users (id),
    UNIQUE (booking_id, reviewer_id)
);

CREATE TABLE IF NOT EXISTS booking_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    sitter_id INTEGER NOT NULL,
    FOREIGN KEY (booking_id) REFERENCES bookings (id),
    FOREIGN KEY (sitter_id) REFERENCES users (id),
    UNIQUE (booking_id, sitter_id)
);