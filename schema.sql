CREATE TABLE IF NOT EXISTS "Users" (
    "t_id" INTEGER NOT NULL UNIQUE,
    "username" TEXT UNIQUE,
    "score" INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS "Teams" (
    "name" TEXT NOT NULL UNIQUE,
    PRIMARY KEY("name")
);

CREATE TABLE IF NOT EXISTS "Games" (
    "id" INTEGER NOT NULL UNIQUE,
    "team_a" TEXT,
    "team_b" TEXT,
    "goals_a" INTEGER,
    "goals_b" INTEGER,
    "isPlayed" INTEGER COLLATE BINARY,
    PRIMARY KEY("id" AUTOINCREMENT),
    FOREIGN KEY("team_b") REFERENCES "Teams"("name"),
    FOREIGN KEY("team_a") REFERENCES "Teams"("name")
);

CREATE TABLE IF NOT EXISTS "Predictions" (
    "user" INTEGER NOT NULL,
    "game" INTEGER NOT NULL,
    "pred_a" INTEGER,
    "pred_b" INTEGER,
    "score" INTEGER,
    PRIMARY KEY("user","game"),
    FOREIGN KEY("user") REFERENCES "Users"("t_id"),
    FOREIGN KEY("game") REFERENCES "Games"("id")
);
