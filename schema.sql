CREATE TABLE IF NOT EXISTS "Users" (
    "t_id" INTEGER NOT NULL UNIQUE,
    "username" TEXT UNIQUE,
    "score" INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS "Teams" (
    "Name" TEXT NOT NULL UNIQUE,
    PRIMARY KEY("Name")
);

CREATE TABLE IF NOT EXISTS "Games" (
    "id" INTEGER NOT NULL UNIQUE,
    "team1" TEXT,
    "team2" TEXT,
    "res1" INTEGER,
    "res2" INTEGER,
    "isPlayed" INTEGER COLLATE BINARY,
    PRIMARY KEY("id" AUTOINCREMENT),
    FOREIGN KEY("team2") REFERENCES "Teams"("Name"),
    FOREIGN KEY("team1") REFERENCES "Teams"("Name")
);

CREATE TABLE IF NOT EXISTS "Predictions" (
    "user" INTEGER NOT NULL,
    "game" INTEGER NOT NULL,
    "pred1" INTEGER,
    "pred2" INTEGER,
    "score" INTEGER,
    PRIMARY KEY("user","game"),
    FOREIGN KEY("user") REFERENCES "Users"("t_id"),
    FOREIGN KEY("game") REFERENCES "Games"("id")
);
