-- Synthetic evaluation fixture: transfer-core 2.2, not an observed production database.
CREATE TABLE warehouses (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE items (
    sku TEXT PRIMARY KEY,
    label TEXT NOT NULL
);
CREATE TABLE stock (
    warehouse_id TEXT NOT NULL,
    sku TEXT NOT NULL,
    pieces INTEGER NOT NULL CHECK (pieces >= 0),
    PRIMARY KEY (warehouse_id, sku),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
);
CREATE TABLE transfers (
    id INTEGER PRIMARY KEY,
    request_key TEXT NOT NULL UNIQUE,
    source_warehouse TEXT NOT NULL,
    destination_warehouse TEXT NOT NULL,
    sku TEXT NOT NULL,
    pieces INTEGER NOT NULL CHECK (pieces > 0),
    status TEXT NOT NULL CHECK (status IN ('in_transit', 'received')),
    CHECK (source_warehouse <> destination_warehouse),
    FOREIGN KEY (sku) REFERENCES items(sku)
);
