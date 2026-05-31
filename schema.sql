CREATE TABLE IF NOT EXISTS "Users" (
    "t_id" INTEGER NOT NULL UNIQUE,
    "username" TEXT UNIQUE,
    "score" INTEGER DEFAULT 0,
    PRIMARY KEY("t_id")
);

CREATE TABLE IF NOT EXISTS "Predictions" (
    "user" INTEGER NOT NULL,
    "game" INTEGER NOT NULL,
    "pred_a" INTEGER,
    "pred_b" INTEGER,
    "score" INTEGER,
    PRIMARY KEY("user", "game"),
    FOREIGN KEY("user") REFERENCES "Users"("t_id") ON DELETE CASCADE
);
