CREATE TABLE IF NOT EXISTS "Users" (
    "t_id" INTEGER NOT NULL UNIQUE,
    "username" TEXT UNIQUE,
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
    "played_at" TEXT,
    "isPlayed" INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY("id" AUTOINCREMENT),
    FOREIGN KEY("team_a") REFERENCES "Teams"("name"),
    FOREIGN KEY("team_b") REFERENCES "Teams"("name")
);

CREATE TABLE IF NOT EXISTS "Groups" (
    "chat_id" INTEGER NOT NULL UNIQUE,
    "title" TEXT,
    "is_verified" INTEGER NOT NULL DEFAULT 0,
    "requested_by" INTEGER,
    PRIMARY KEY("chat_id")
);

CREATE TABLE IF NOT EXISTS "Predictions" (
    "user" INTEGER NOT NULL,
    "game" INTEGER NOT NULL,
    "group_id" INTEGER NOT NULL,
    "pred_a" INTEGER,
    "pred_b" INTEGER,
    "score" INTEGER,
    PRIMARY KEY("user", "game", "group_id"),
    FOREIGN KEY("user") REFERENCES "Users"("t_id") ON DELETE CASCADE,
    FOREIGN KEY("game") REFERENCES "Games"("id") ON DELETE CASCADE,
    FOREIGN KEY("group_id") REFERENCES "Groups"("chat_id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "UserGroupScores" (
    "user_id" INTEGER NOT NULL,
    "group_id" INTEGER NOT NULL,
    "score" INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY("user_id", "group_id"),
    FOREIGN KEY("user_id") REFERENCES "Users"("t_id") ON DELETE CASCADE,
    FOREIGN KEY("group_id") REFERENCES "Groups"("chat_id") ON DELETE CASCADE
);
