CREATE TABLE IF NOT EXISTS "Users" (
    "t_id" INTEGER NOT NULL UNIQUE,
    "username" TEXT UNIQUE,
    "score" INTEGER DEFAULT 0,
    PRIMARY KEY("t_id")
);

CREATE TABLE IF NOT EXISTS "Teams" (
    "name" TEXT NOT NULL UNIQUE,
    PRIMARY KEY("name")
);

CREATE TABLE IF NOT EXISTS "Games" (
    "id" INTEGER NOT NULL UNIQUE,
    "team_a" TEXT NOT NULL,
    "team_b" TEXT NOT NULL,
    "goals_a" INTEGER NOT NULL DEFAULT 0,
    "goals_b" INTEGER NOT NULL DEFAULT 0,
    "isPlayed" INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY("id" AUTOINCREMENT),
    FOREIGN KEY("team_a") REFERENCES "Teams"("name"),
    FOREIGN KEY("team_b") REFERENCES "Teams"("name")
);

CREATE TABLE IF NOT EXISTS "Predictions" (
    "user" INTEGER NOT NULL,
    "game" INTEGER NOT NULL,
    "pred_a" INTEGER,
    "pred_b" INTEGER,
    "score" INTEGER,
    PRIMARY KEY("user", "game"),
    FOREIGN KEY("user") REFERENCES "Users"("t_id") ON DELETE CASCADE,
    FOREIGN KEY("game") REFERENCES "Games"("id") ON DELETE CASCADE
);
