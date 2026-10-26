-- Airbnb analytics schema (PostgreSQL 14+).
-- Columns marked SENSITIVE are never granted to the read-only analyst role.

CREATE TABLE IF NOT EXISTS neighbourhoods (
    neighbourhood_id   SERIAL PRIMARY KEY,
    neighbourhood      TEXT NOT NULL,
    city               TEXT NOT NULL,
    UNIQUE (neighbourhood, city)
);

CREATE TABLE IF NOT EXISTS hosts (
    host_id                 INTEGER PRIMARY KEY,
    host_name               TEXT NOT NULL,
    host_since              DATE NOT NULL,
    host_is_superhost       BOOLEAN NOT NULL DEFAULT FALSE,
    host_response_rate      NUMERIC(5, 2),
    host_identity_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    host_email              TEXT,          -- SENSITIVE
    host_phone              TEXT           -- SENSITIVE
);

CREATE TABLE IF NOT EXISTS listings (
    listing_id         INTEGER PRIMARY KEY,
    host_id            INTEGER NOT NULL REFERENCES hosts (host_id),
    neighbourhood_id   INTEGER NOT NULL REFERENCES neighbourhoods (neighbourhood_id),
    name               TEXT NOT NULL,
    room_type          TEXT NOT NULL CHECK (room_type IN ('Entire home/apt', 'Private room', 'Shared room', 'Hotel room')),
    property_type      TEXT NOT NULL,
    accommodates       INTEGER NOT NULL,
    bedrooms           INTEGER,
    bathrooms          NUMERIC(3, 1),
    beds               INTEGER,
    price              NUMERIC(10, 2) NOT NULL,   -- nightly price in USD
    cleaning_fee       NUMERIC(10, 2),
    minimum_nights     INTEGER NOT NULL,
    availability_365   INTEGER NOT NULL,
    instant_bookable   BOOLEAN NOT NULL,
    latitude           NUMERIC(9, 6),
    longitude          NUMERIC(9, 6),
    created_at         DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS amenities (
    amenity_id   SERIAL PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS listing_amenities (
    listing_id   INTEGER NOT NULL REFERENCES listings (listing_id),
    amenity_id   INTEGER NOT NULL REFERENCES amenities (amenity_id),
    PRIMARY KEY (listing_id, amenity_id)
);

CREATE TABLE IF NOT EXISTS guests (
    guest_id      INTEGER PRIMARY KEY,
    guest_name    TEXT NOT NULL,
    country       TEXT NOT NULL,
    signup_date   DATE NOT NULL,
    email         TEXT                -- SENSITIVE
);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id      INTEGER PRIMARY KEY,
    listing_id      INTEGER NOT NULL REFERENCES listings (listing_id),
    guest_id        INTEGER NOT NULL REFERENCES guests (guest_id),
    check_in        DATE NOT NULL,
    check_out       DATE NOT NULL,
    nights          INTEGER NOT NULL,
    guests_count    INTEGER NOT NULL,
    total_price     NUMERIC(10, 2) NOT NULL,
    payment_method  TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('confirmed', 'completed', 'cancelled')),
    booked_at       TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id       INTEGER PRIMARY KEY,
    listing_id      INTEGER NOT NULL REFERENCES listings (listing_id),
    guest_id        INTEGER NOT NULL REFERENCES guests (guest_id),
    booking_id      INTEGER REFERENCES bookings (booking_id),
    review_date     DATE NOT NULL,
    rating          INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    cleanliness     INTEGER CHECK (cleanliness BETWEEN 1 AND 5),
    communication   INTEGER CHECK (communication BETWEEN 1 AND 5),
    location        INTEGER CHECK (location BETWEEN 1 AND 5),
    value           INTEGER CHECK (value BETWEEN 1 AND 5),
    comments        TEXT
);

CREATE INDEX IF NOT EXISTS idx_listings_host ON listings (host_id);
CREATE INDEX IF NOT EXISTS idx_listings_neighbourhood ON listings (neighbourhood_id);
CREATE INDEX IF NOT EXISTS idx_listings_room_type ON listings (room_type);
CREATE INDEX IF NOT EXISTS idx_bookings_listing ON bookings (listing_id);
CREATE INDEX IF NOT EXISTS idx_bookings_guest ON bookings (guest_id);
CREATE INDEX IF NOT EXISTS idx_bookings_check_in ON bookings (check_in);
CREATE INDEX IF NOT EXISTS idx_reviews_listing ON reviews (listing_id);
CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews (review_date);
