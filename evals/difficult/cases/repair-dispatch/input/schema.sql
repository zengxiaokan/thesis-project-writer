-- Synthetic evaluation fixture, release 2.0; definition only, not migration history.
CREATE TABLE worker (
    id INTEGER PRIMARY KEY,
    region TEXT NOT NULL,
    available INTEGER NOT NULL CHECK(available IN (0,1)),
    active_load INTEGER NOT NULL DEFAULT 0 CHECK(active_load >= 0)
);
CREATE TABLE ticket (
    id INTEGER PRIMARY KEY,
    region TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('open','assigned','closed')),
    worker_id INTEGER REFERENCES worker(id),
    version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE receipt (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL UNIQUE REFERENCES ticket(id),
    worker_id INTEGER NOT NULL REFERENCES worker(id),
    status TEXT NOT NULL CHECK(status IN ('pending','sent')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0)
);
