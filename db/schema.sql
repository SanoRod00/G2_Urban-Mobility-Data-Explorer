
CREATE TABLE IF NOT EXISTS zones(
   zone_id INTEGER PRIMARY KEY,
   zone_name TEXT,
   borough TEXT,
   service_zone TEXT,
   longitude REAL,
   latitude REAL
 
);

CREATE TABLE IF NOT EXISTS payment_type(
    payment_type_id INTEGER PRIMARY KEY,
    description TEXT NOT NULL 
);

CREATE TABLE IF NOT EXISTS rate_codes(
    rate_codes_id INTEGER PRIMARY KEY,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendors(
    vendor_id INTEGER PRIMARY KEY, 
    vendor_name TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trips(
    trip_id INTEGER PRIMARY KEY,
    vendor_id INTEGER,
    pickup_datetime TEXT NOT NULL,
    dropoff_datetime TEXT NOT NULL,
    pickup_zone INTEGER NOT NULL,
    dropoff_zone INTEGER NOT NULL,
    payment_type_id INTEGER NOT NULL,
    rate_codes_id INTEGER NOT NULL,
    fare_amount REAL NOT NULL,
    trip_duration REAL NOT NULL,
    trip_distance REAL NOT NULL,
    passenger_count INTEGER,
    tolls REAL,
    extra REAL,
    mta_tax REAL,
    tip REAL,
    improvement_surcharge REAL,
    congestion_surcharge REAL,
    total_amount REAL NOT NULL,
    avg_speed_mph REAL,
    revenue_per_minute REAL,
    fare_per_mile REAL,
    tip_percentage REAL,
    pickup_hour INTEGER NOT NULL,
    pickup_weekday INTEGER NOT NULL,
    time_of_day TEXT NOT NULL,
    unknown_zone_flag INTEGER NOT NULL,

    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id),
    FOREIGN KEY (payment_type_id) REFERENCES payment_type(payment_type_id),
    FOREIGN KEY (rate_codes_id) REFERENCES rate_codes(rate_codes_id),
    FOREIGN KEY (pickup_zone) REFERENCES zones(zone_id),
    FOREIGN KEY (dropoff_zone) REFERENCES zones(zone_id),

    CHECK (dropoff_datetime > pickup_datetime),
    CHECK (fare_amount > 0 AND total_amount > 0),
    CHECK (trip_distance >= 0 AND trip_distance <= 100),
    CHECK (pickup_hour BETWEEN 0 AND 23),
    CHECK (pickup_weekday BETWEEN 1 AND 7),
    CHECK (time_of_day IN ('night', 'morning_rush', 'midday', 'evening_rush', 'evening')),
    CHECK (unknown_zone_flag IN (0, 1))

);

CREATE TABLE IF NOT EXISTS agg_zone_weekday_hour(
    pickup_zone INTEGER NOT NULL,
    weekday INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    trip_count INTEGER NOT NULL,
    total_revenue REAL NOT NULL,
    total_minutes REAL NOT NULL,


    PRIMARY KEY (pickup_zone, weekday, hour),
    FOREIGN KEY (pickup_zone) REFERENCES zones(zone_id),

    CHECK (weekday BETWEEN 1 AND 7),
    CHECK (hour BETWEEN 0 AND 23)
);

CREATE TABLE IF NOT EXISTS agg_flatfare_hourly(
    manhatta_zone INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    dist_band INTEGER NOT NULL,
    metered_trips INTEGER NOT NULL,
    metered_fare_sum REAL NOT NULL,
    metered_over_flat INTEGER NOT NULL,

    primary key (manhattan_zone, hour, dist_band),
    FOREIGN KEY (manhattan_zone) REFERENCES zones(zone_id),

    CHHECK (hour BETWEEN 0 AND 23)
);

