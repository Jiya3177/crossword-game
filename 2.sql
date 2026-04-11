CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scores (
    score_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    score INTEGER NOT NULL,
    answered_cells INTEGER NOT NULL DEFAULT 0,
    total_cells INTEGER NOT NULL DEFAULT 0,
    time_taken INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

DROP VIEW IF EXISTS leaderboard_view;

CREATE VIEW leaderboard_view AS
SELECT
    u.username,
    best.score AS best_score,
    best.answered_cells AS best_answered_cells,
    best.total_cells AS best_total_cells,
    best.time_taken AS best_time,
    totals.games_played
FROM users u
JOIN (
    SELECT
        s1.user_id,
        s1.score,
        s1.answered_cells,
        s1.total_cells,
        s1.time_taken,
        s1.score_id
    FROM scores s1
    WHERE s1.score_id = (
        SELECT s2.score_id
        FROM scores s2
        WHERE s2.user_id = s1.user_id
        ORDER BY s2.score DESC, s2.time_taken ASC, s2.score_id ASC
        LIMIT 1
    )
) best ON u.user_id = best.user_id
JOIN (
    SELECT user_id, COUNT(*) AS games_played
    FROM scores
    GROUP BY user_id
) totals ON u.user_id = totals.user_id
ORDER BY best.score DESC, best.time_taken ASC
LIMIT 10;
