-- FreightIQ High-Concurrency SQLite Database Schema with WAL Mode

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    phone TEXT UNIQUE,
    company TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'Chartering Officer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cargo_queries (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    origin_port TEXT NOT NULL,
    destination_port TEXT NOT NULL,
    cargo_type TEXT NOT NULL,
    cargo_volume_mt NUMERIC NOT NULL,
    vessel_preference TEXT NOT NULL,
    contract_horizon TEXT NOT NULL,
    forecasted_rate_usd NUMERIC,
    recommended_vessel TEXT,
    risk_tier TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS weather_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    port_name TEXT NOT NULL,
    wind_speed_knots REAL,
    wave_height_m REAL,
    rainfall_mm REAL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS port_queues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    port_name TEXT NOT NULL,
    berths_occupied INTEGER,
    vessels_waiting INTEGER,
    avg_turnaround_hrs REAL,
    congestion_score REAL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    action TEXT NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for lightning-fast lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
CREATE INDEX IF NOT EXISTS idx_queries_route ON cargo_queries(origin_port, destination_port);
