"""Read-only queries on vct/data/vct_site.sqlite (made by vct-ratings' model/export_site.py).

Probabilities and credits are stored in basis points; everything returned here is in percent.
"""
import sqlite3
from contextlib import closing
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "vct_site.sqlite"


def _conn():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _all(sql, params=()):
    with closing(_conn()) as c:
        return [dict(r) for r in c.execute(sql, params)]


def _one(sql, params=()):
    rows = _all(sql, params)
    return rows[0] if rows else None


def pct(bp):
    return None if bp is None else bp / 100


def meta():
    return {r["key"]: r["value"] for r in _all("SELECT key, value FROM meta")}


def years():
    return [int(y) for y in meta()["years"].split(",")]


def scopes():
    """(scope, label) for every year on its own and all years together; newest year first."""
    ys = years()
    return [("all", f"All years ({ys[0]}–{ys[-1]})")] + [(f"y{y}", str(y)) for y in reversed(ys)]


def events():
    return _all("""SELECT e.*, COUNT(m.match_id) AS matches,
                          EXISTS (SELECT 1 FROM leaderboard WHERE scope = 'e' || e.event_id) AS has_wpa
                   FROM events e JOIN matches m USING (event_id)
                   GROUP BY e.event_id ORDER BY e.first_match""")


def event(event_id):
    return _one("SELECT * FROM events WHERE event_id = ?", (event_id,))


MATCH_SQL = """SELECT m.*, t1.name AS team1, t1.tag AS team1_tag, t2.name AS team2, t2.tag AS team2_tag,
                      e.name AS event
               FROM matches m JOIN teams t1 ON t1.team_id = m.team1_id JOIN teams t2 ON t2.team_id = m.team2_id
               JOIN events e USING (event_id)"""


def event_matches(event_id):
    return _all(MATCH_SQL + " WHERE m.event_id = ? ORDER BY m.start_time DESC", (event_id,))


def match(match_id):
    m = _one(MATCH_SQL + " WHERE m.match_id = ?", (match_id,))
    if not m:
        return None
    m["maps"] = _all("SELECT * FROM maps WHERE match_id = ? ORDER BY map_number", (match_id,))
    for mp in m["maps"]:
        mp["rounds"] = _all("""SELECT round_num, winner_id, outcome, team1_score, team2_score,
                                      start_prob IS NOT NULL AS has_trace
                               FROM rounds WHERE game_id = ? ORDER BY round_num""", (mp["game_id"],))
    return m


def _describe(a, names, tags):
    actor = names.get(a["actor_id"], "?")
    victim = names.get(a["victim_id"], "?")
    team = tags.get(a["actor_team_id"], "")
    if a["type"] == "plant":
        return f"{actor} ({team}) plants {a['site'] or ''}".strip()
    if a["type"] == "defuse":
        return f"{actor} ({team}) defuses"
    if a["action"] == "environment_death":
        return f"{victim} ({tags.get(a['victim_team_id'], '')}) dies"
    if a["action"] == "spike_death":
        return f"{victim} ({tags.get(a['victim_team_id'], '')}) dies to the spike"
    return f"{actor} ({team}) kills {victim}"


TAGS = {"opening_kill": "opening kill", "trade_kill": "trade", "teamkill": "teamkill"}


def round_detail(game_id, round_num):
    r = _one("""SELECT r.*, mp.match_id, mp.map_name, mp.map_number, mp.team1_score AS map_team1_score,
                       mp.team2_score AS map_team2_score
                FROM rounds r JOIN maps mp USING (game_id) WHERE r.game_id = ? AND r.round_num = ?""",
             (game_id, round_num))
    if not r:
        return None
    r["match"] = _one(MATCH_SQL + " WHERE m.match_id = ?", (r["match_id"],))
    m = r["match"]
    r["defender_id"] = m["team2_id"] if r["attacker_id"] == m["team1_id"] else m["team1_id"]
    tags = {m["team1_id"]: m["team1_tag"] or m["team1"], m["team2_id"]: m["team2_tag"] or m["team2"]}
    r["attacker_tag"], r["defender_tag"] = tags[r["attacker_id"]], tags[r["defender_id"]]
    r["winner_tag"] = tags.get(r["winner_id"])
    nav = _one("""SELECT MAX(CASE WHEN round_num < ? THEN round_num END) AS prev,
                         MIN(CASE WHEN round_num > ? THEN round_num END) AS next
                  FROM rounds WHERE game_id = ? AND start_prob IS NOT NULL""", (round_num, round_num, game_id))
    r.update(nav)

    actions = _all("SELECT * FROM actions WHERE game_id = ? AND round_num = ? ORDER BY event_num",
                   (game_id, round_num))
    ids = {a[k] for a in actions for k in ("actor_id", "victim_id") if a[k]}
    names = {p["player_id"]: p["name"] for p in
             _all(f"SELECT * FROM players WHERE player_id IN ({','.join('?' * len(ids))})", tuple(ids))} if ids else {}
    for i, a in enumerate(actions):
        a["text"] = _describe(a, names, tags)
        a["tag"] = TAGS.get(a["action"], "")
        if i == len(actions) - 1 and a["prob_after"] in (0, 10000):
            a["tag"] = (a["tag"] + ", round over") if a["tag"] else "round over"
        for k in ("prob_before", "prob_after", "actor_credit", "victim_credit"):
            a[k] = pct(a[k])
        a["change"] = a["prob_after"] - a["prob_before"]
        a["clock"] = f"{a['time_seconds'] // 60}:{a['time_seconds'] % 60:02d}" if a["time_seconds"] is not None else ""
    r["actions"] = actions
    r["start_prob"] = pct(r["start_prob"])

    # Chart points: round start, then each action's before -> after at its time.
    points = [{"x": 0, "y": r["start_prob"], "label": "Round start"}] if r["start_prob"] is not None else []
    for a in actions:
        t = a["time_seconds"] or 0
        points.append({"x": t, "y": a["prob_before"], "label": ""})
        points.append({"x": t, "y": a["prob_after"], "label": a["text"]})
    r["points"] = points
    return r


def plays(scope, kind, limit):
    rows = _all("""SELECT p.*, pl.name AS player, t.tag AS team, mp.map_name, mp.map_number, e.name AS event,
                          m.stage, a.weapon, a.prob_before, a.prob_after, a.action,
                          a.actor_team_id = r.attacker_id AS actor_attacking,
                          CASE WHEN m.team1_id = p.team_id THEN t2.tag ELSE t1.tag END AS opponent,
                          CASE WHEN m.team1_id = p.team_id THEN m.team1_score ELSE m.team2_score END AS maps_won,
                          CASE WHEN m.team1_id = p.team_id THEN m.team2_score ELSE m.team1_score END AS maps_lost,
                          CASE WHEN m.team1_id = p.team_id THEN mp.team1_score ELSE mp.team2_score END AS rounds_won,
                          CASE WHEN m.team1_id = p.team_id THEN mp.team2_score ELSE mp.team1_score END AS rounds_lost
                   FROM plays p JOIN players pl USING (player_id) JOIN teams t ON t.team_id = p.team_id
                   JOIN matches m ON m.match_id = p.match_id JOIN events e USING (event_id)
                   JOIN teams t1 ON t1.team_id = m.team1_id JOIN teams t2 ON t2.team_id = m.team2_id
                   LEFT JOIN maps mp ON mp.game_id = p.game_id
                   LEFT JOIN actions a ON a.game_id = p.game_id AND a.round_num = p.round_num
                                      AND a.event_num = p.event_num
                   LEFT JOIN rounds r ON r.game_id = p.game_id AND r.round_num = p.round_num
                   WHERE p.scope = ? AND p.kind = ? ORDER BY p.rank LIMIT ?""", (scope, kind, limit))
    for r in rows:
        r["credit"] = pct(r["credit"])
        r["prob_before"], r["prob_after"] = pct(r["prob_before"]), pct(r["prob_after"])
        if r["prob_before"] is not None and not r["actor_attacking"]:  # killer's team's odds
            r["prob_before"], r["prob_after"] = 100 - r["prob_before"], 100 - r["prob_after"]
        r["per_round"] = r["credit"] / r["rounds"] if r["rounds"] else None
    return rows


def leaderboard(scope, min_rounds):
    return _all("""SELECT l.*, p.name AS player FROM leaderboard l JOIN players p USING (player_id)
                   WHERE l.scope = ? AND l.wpa_rounds >= ? ORDER BY l.shrunk DESC""", (scope, min_rounds))
