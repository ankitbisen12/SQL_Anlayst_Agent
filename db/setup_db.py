"""
Set up the Airbnb analytics database: schema, seed data and the read-only role used by the agent.

Works the same for a local Docker Postgres, Neon, Supabase or any other PostgreSQL 14+ server.

    uv run python db/setup_db.py            # create schema + seed (if empty) + read-only role
    uv run python db/setup_db.py --reset    # drop everything and re-seed

Environment:
    ADMIN_DATABASE_URL    owner / admin connection string (used ONLY by this script, never by the agent)
    ANALYST_RO_USER       read-only role name        (default: analyst_ro)
    ANALYST_RO_PASSWORD   read-only role password    (required)
"""

import argparse
import datetime as dt
import os
import random
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql

sys.path.append(str(Path(__file__).resolve().parent.parent))
from utils.config import encode_db_url_password, get_settings  # noqa: E402

load_dotenv()

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
TABLES = ["reviews", "bookings", "listing_amenities", "amenities", "listings", "guests", "hosts", "neighbourhoods"]

CITIES = {
    "New York": (40.73, -73.95, 1.35, ["Williamsburg", "Harlem", "Upper West Side", "East Village", "Astoria", "Bushwick", "Chelsea", "SoHo"]),
    "Los Angeles": (34.05, -118.25, 1.15, ["Venice", "Hollywood", "Santa Monica", "Silver Lake", "Downtown", "Echo Park"]),
    "San Francisco": (37.77, -122.42, 1.40, ["Mission District", "SoMa", "Nob Hill", "Haight-Ashbury", "Marina", "Castro"]),
    "Chicago": (41.88, -87.63, 0.85, ["Lincoln Park", "Wicker Park", "Logan Square", "The Loop", "Lakeview"]),
    "Austin": (30.27, -97.74, 0.95, ["South Congress", "East Austin", "Downtown", "Zilker", "Hyde Park"]),
    "Seattle": (47.61, -122.33, 1.05, ["Capitol Hill", "Ballard", "Fremont", "Queen Anne", "Belltown"]),
}
ROOM_TYPES = [("Entire home/apt", 0.58, 1.0), ("Private room", 0.32, 0.48), ("Shared room", 0.05, 0.28), ("Hotel room", 0.05, 0.9)]
PROPERTY_TYPES = {
    "Entire home/apt": ["Apartment", "House", "Condo", "Loft", "Townhouse", "Guest suite"],
    "Private room": ["Apartment", "House", "Townhouse", "Bed and breakfast"],
    "Shared room": ["Apartment", "Hostel", "House"],
    "Hotel room": ["Boutique hotel", "Hotel"],
}
AMENITIES = ["Wifi", "Kitchen", "Air conditioning", "Heating", "Washer", "Dryer", "Free parking", "Pool",
             "Hot tub", "Gym", "Pets allowed", "Workspace", "TV", "Self check-in", "Balcony", "EV charger"]
PAYMENT_METHODS = [("Credit Card", 0.55), ("Debit Card", 0.15), ("PayPal", 0.14), ("Apple Pay", 0.08),
                   ("Google Pay", 0.05), ("Airbnb Gift Card", 0.03)]
COUNTRIES = [("United States", 0.45), ("United Kingdom", 0.09), ("Canada", 0.08), ("Germany", 0.07),
             ("France", 0.06), ("India", 0.06), ("Australia", 0.05), ("Japan", 0.04), ("Brazil", 0.04),
             ("Mexico", 0.03), ("Spain", 0.03)]
FIRST = ["James", "Mary", "Liam", "Olivia", "Noah", "Emma", "Aarav", "Priya", "Lucas", "Sofia", "Mateo", "Mia",
         "Wei", "Yuki", "Omar", "Fatima", "Ethan", "Ava", "Diego", "Chloe", "Arjun", "Zara", "Leo", "Nora"]
LAST = ["Smith", "Johnson", "Garcia", "Patel", "Kim", "Nguyen", "Brown", "Lopez", "Müller", "Rossi", "Sharma",
        "Tanaka", "Silva", "Martin", "Wilson", "Khan", "Chen", "Davis", "Moreau", "Singh"]
ADJ = ["Cozy", "Sunny", "Modern", "Charming", "Spacious", "Stylish", "Quiet", "Bright", "Rustic", "Luxury"]
NOUN = {"Entire home/apt": ["apartment", "home", "loft", "retreat", "flat"], "Private room": ["room", "bedroom", "suite"],
        "Shared room": ["shared room", "bunk"], "Hotel room": ["hotel room", "king room", "studio"]}
REVIEW_TEXT = {
    5: ["Absolutely loved our stay!", "Perfect location and spotless.", "Host was amazing, would come back.", "Even better than the photos."],
    4: ["Great place, minor issues with noise.", "Very comfortable, good value.", "Nice stay overall."],
    3: ["It was okay, a bit smaller than expected.", "Average experience, check-in was slow."],
    2: ["Not very clean on arrival.", "Wifi kept dropping and the host was slow to reply."],
    1: ["Terrible experience, would not recommend.", "Place did not match the listing at all."],
}


def weighted(rng: random.Random, options: list[tuple]) -> tuple:
    return rng.choices(options, weights=[o[1] for o in options], k=1)[0]


def random_date(rng: random.Random, start: dt.date, end: dt.date) -> dt.date:
    return start + dt.timedelta(days=rng.randint(0, (end - start).days))


def generate_data(seed: int = 42, n_hosts: int = 400, n_listings: int = 2000, n_guests: int = 3000, n_bookings: int = 15000) -> dict:
    """Deterministic synthetic Airbnb data (same seed -> same data, so evals are reproducible)."""
    rng = random.Random(seed)
    data: dict[str, list[tuple]] = {}

    neighbourhoods = []
    for city, (_, _, _, hoods) in CITIES.items():
        neighbourhoods.extend((len(neighbourhoods) + 1, hood, city) for hood in hoods)
    data["neighbourhoods"] = neighbourhoods

    hosts = []
    for host_id in range(1, n_hosts + 1):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        hosts.append((
            host_id, f"{first} {last}", random_date(rng, dt.date(2012, 1, 1), dt.date(2024, 6, 30)),
            rng.random() < 0.28, round(rng.uniform(60, 100), 2), rng.random() < 0.8,
            f"{first.lower()}.{last.lower()}{host_id}@example.com", f"+1 555-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}",
        ))
    data["hosts"] = hosts

    listings, listing_meta = [], {}
    for listing_id in range(1, n_listings + 1):
        hood = rng.choice(neighbourhoods)
        lat0, lon0, city_factor, _ = CITIES[hood[2]]
        room_type, _, room_factor = weighted(rng, ROOM_TYPES)
        accommodates = rng.randint(1, 2) if room_type in ("Shared room", "Private room") else rng.randint(2, 10)
        bedrooms = 0 if room_type == "Shared room" else max(1, accommodates // 2)
        price = round(max(25, rng.gauss(165, 45) * city_factor * room_factor * (1 + accommodates * 0.06)), 2)
        listings.append((
            listing_id, rng.randint(1, n_hosts), hood[0],
            f"{rng.choice(ADJ)} {rng.choice(NOUN[room_type])} in {hood[1]}",
            room_type, rng.choice(PROPERTY_TYPES[room_type]), accommodates, bedrooms,
            rng.choice([1, 1, 1.5, 2, 2.5]) if room_type == "Entire home/apt" else 1, max(1, bedrooms + rng.randint(0, 2)),
            price, round(price * rng.uniform(0.1, 0.35), 2), rng.choice([1, 1, 2, 2, 3, 5, 7, 30]),
            rng.randint(0, 365), rng.random() < 0.45,
            round(lat0 + rng.uniform(-0.08, 0.08), 6), round(lon0 + rng.uniform(-0.08, 0.08), 6),
            random_date(rng, dt.date(2015, 1, 1), dt.date(2024, 12, 31)),
        ))
        listing_meta[listing_id] = (price, accommodates)
    data["listings"] = listings

    data["amenities"] = [(i, name) for i, name in enumerate(AMENITIES, start=1)]
    data["listing_amenities"] = [
        (listing_id, amenity_id)
        for listing_id in range(1, n_listings + 1)
        for amenity_id in sorted(rng.sample(range(1, len(AMENITIES) + 1), rng.randint(3, 10)))
    ]

    guests = []
    for guest_id in range(1, n_guests + 1):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        guests.append((
            guest_id, f"{first} {last}", weighted(rng, COUNTRIES)[0],
            random_date(rng, dt.date(2016, 1, 1), dt.date(2025, 6, 30)),
            f"{first.lower()}{guest_id}@example.com",
        ))
    data["guests"] = guests

    # Bookings with summer seasonality
    month_weights = [0.6, 0.6, 0.8, 0.9, 1.0, 1.3, 1.5, 1.5, 1.1, 0.9, 0.8, 1.0]
    bookings = []
    for booking_id in range(1, n_bookings + 1):
        listing_id = rng.randint(1, n_listings)
        price, accommodates = listing_meta[listing_id]
        year = rng.choice([2023, 2024, 2025])
        month = rng.choices(range(1, 13), weights=month_weights, k=1)[0]
        check_in = dt.date(year, month, rng.randint(1, 28))
        nights = rng.choice([1, 2, 2, 3, 3, 4, 5, 7, 14])
        status = "cancelled" if rng.random() < 0.08 else ("confirmed" if check_in > dt.date(2025, 10, 1) else "completed")
        booked_at = dt.datetime.combine(check_in - dt.timedelta(days=rng.randint(1, 120)), dt.time(rng.randint(0, 23), rng.randint(0, 59)))
        bookings.append((
            booking_id, listing_id, rng.randint(1, n_guests), check_in, check_in + dt.timedelta(days=nights),
            nights, rng.randint(1, accommodates), round(price * nights, 2), weighted(rng, PAYMENT_METHODS)[0], status, booked_at,
        ))
    data["bookings"] = bookings

    reviews = []
    for booking in bookings:
        if booking[9] != "completed" or rng.random() > 0.6:
            continue
        rating = rng.choices([5, 4, 3, 2, 1], weights=[52, 30, 10, 5, 3], k=1)[0]
        comment = rng.choice(REVIEW_TEXT[rating])
        if rng.random() < 0.01:  # a few reviews leak contact details -> exercised by the PII output guardrail
            comment += f" Contact me at guest{booking[2]}@example.com or +1 555-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}."
        review_date = booking[4] + dt.timedelta(days=rng.randint(1, 14))
        sub_scores = [max(1, min(5, rating + rng.choice([-1, 0, 0, 1]))) for _ in range(4)]
        reviews.append((len(reviews) + 1, booking[1], booking[2], booking[0], review_date, rating, *sub_scores, comment))
    data["reviews"] = reviews
    return data


def copy_rows(cur: psycopg.Cursor, table: str, rows: list[tuple]) -> None:
    cur.execute(sql.SQL("SELECT * FROM {} LIMIT 0").format(sql.Identifier(table)))
    columns = [d.name for d in cur.description]
    with cur.copy(sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns))
    )) as copy:
        for row in rows:
            copy.write_row(row)


def setup_readonly_role(cur: psycopg.Cursor, dbname: str, role: str, password: str) -> None:
    settings = get_settings()
    sensitive = settings.sensitive_column_set

    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    action = "ALTER" if cur.fetchone() else "CREATE"
    cur.execute(sql.SQL(action + " ROLE {} WITH LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(
        sql.Identifier(role), sql.Literal(password)))

    # Defence in depth: every session of this role is read-only and time-limited.
    cur.execute(sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(sql.Identifier(role)))
    cur.execute(sql.SQL("ALTER ROLE {} SET statement_timeout = {}").format(
        sql.Identifier(role), sql.Literal(f"{settings.db_statement_timeout_ms}ms")))
    cur.execute(sql.SQL("ALTER ROLE {} SET idle_in_transaction_session_timeout = '30s'").format(sql.Identifier(role)))

    cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(dbname), sql.Identifier(role)))
    cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
    try:
        with cur.connection.transaction():  # savepoint: managed providers may not allow this
            cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    except psycopg.Error as exc:
        print(f"  (skipped REVOKE CREATE ON SCHEMA public: {exc.diag.message_primary})")

    # Column-level grants: sensitive columns are simply not readable by the agent's role.
    for table in TABLES:
        cur.execute(sql.SQL("REVOKE ALL ON {} FROM {}").format(sql.Identifier(table), sql.Identifier(role)))
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
            (table,),
        )
        allowed = [c for (c,) in cur.fetchall() if c.lower() not in sensitive]
        cur.execute(sql.SQL("GRANT SELECT ({}) ON {} TO {}").format(
            sql.SQL(", ").join(map(sql.Identifier, allowed)), sql.Identifier(table), sql.Identifier(role)))


def lock_down_tables(cur: psycopg.Cursor, role: str) -> None:
    """
    Close every path to the data except the read-only agent role.

    Supabase exposes the `public` schema through its auto-generated REST API (PostgREST) to the
    `anon` and `authenticated` roles, and grants them ALL on new tables by default. Without this,
    anyone holding the project's anon key could read - or modify - these tables directly.
    Row Level Security is enabled with a single SELECT policy for the agent role, which is what
    Supabase's Security Advisor expects. On plain Postgres this is harmless (the owner bypasses RLS).
    """
    cur.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
    api_roles = [r for (r,) in cur.fetchall()]
    for table in TABLES:
        ident = sql.Identifier(table)
        for api_role in api_roles:
            cur.execute(sql.SQL("REVOKE ALL ON {} FROM {}").format(ident, sql.Identifier(api_role)))
        cur.execute(sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(ident))
        cur.execute(sql.SQL("DROP POLICY IF EXISTS analyst_read ON {}").format(ident))
        cur.execute(sql.SQL("CREATE POLICY analyst_read ON {} FOR SELECT TO {} USING (true)").format(
            ident, sql.Identifier(role)))
    if api_roles:
        print(f"  revoked API access for: {', '.join(api_roles)} (Supabase detected)")


def print_connection_hint(admin_url: str, role: str) -> None:
    info = psycopg.conninfo.conninfo_to_dict(admin_url)
    host, port, user, dbname = info.get("host", "<host>"), info.get("port", "5432"), info.get("user", ""), info.get("dbname", "postgres")
    # Supabase's pooler identifies the project through the username: postgres.<project-ref>
    suffix = user[user.index("."):] if "pooler.supabase.com" in host and "." in user else ""
    print("Done. Set DATABASE_URL to the read-only role (URL-encode special characters in the password):")
    print(f"  DATABASE_URL=postgresql://{role}{suffix}:<ANALYST_RO_PASSWORD>@{host}:{port}/{dbname}?sslmode=require")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop all tables and re-seed")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    admin_url = encode_db_url_password(os.environ.get("ADMIN_DATABASE_URL", ""))
    password = os.environ.get("ANALYST_RO_PASSWORD")
    role = os.environ.get("ANALYST_RO_USER", "analyst_ro")
    if not admin_url or not password:
        sys.exit("ADMIN_DATABASE_URL and ANALYST_RO_PASSWORD must be set (see .env.example).")

    with psycopg.connect(admin_url) as conn, conn.cursor() as cur:
        if args.reset:
            print("Dropping existing tables ...")
            for table in TABLES:
                cur.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table)))

        print("Creating schema ...")
        cur.execute(SCHEMA_FILE.read_text(encoding="utf-8"))

        cur.execute("SELECT COUNT(*) FROM listings")
        if cur.fetchone()[0] == 0:
            print("Generating seed data ...")
            data = generate_data(seed=args.seed)
            for table in reversed(TABLES):  # parents first
                copy_rows(cur, table, data[table])
                print(f"  {table:<18} {len(data[table]):>7} rows")
            for table, id_col in (("neighbourhoods", "neighbourhood_id"), ("amenities", "amenity_id")):
                cur.execute(sql.SQL("SELECT setval(pg_get_serial_sequence({}, {}), (SELECT MAX({}) FROM {}))").format(
                    sql.Literal(table), sql.Literal(id_col), sql.Identifier(id_col), sql.Identifier(table)))
        else:
            print("Tables already contain data - skipping seed (use --reset to re-seed).")

        print(f"Configuring read-only role '{role}' ...")
        setup_readonly_role(cur, conn.info.dbname, role, password)
        print("Locking down tables (RLS + API roles) ...")
        lock_down_tables(cur, role)
        conn.commit()

    with psycopg.connect(admin_url, autocommit=True) as conn:
        for table in TABLES:
            conn.execute(sql.SQL("ANALYZE {}").format(sql.Identifier(table)))
    print_connection_hint(admin_url, role)


if __name__ == "__main__":
    main()
