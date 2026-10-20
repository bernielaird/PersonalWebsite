"""Read-only queries on vct/data/vct_site.sqlite (made by vct-ratings' model/export_site.py).

Probabilities and credits are stored in basis points; everything returned here is in percent.
"""
import sqlite3
from contextlib import closing
from urllib.parse import urlencode
from pathlib import Path

from .colors import match_style

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
                      t1.primary_color AS team1_primary, t1.secondary_color AS team1_secondary,
                      t2.primary_color AS team2_primary, t2.secondary_color AS team2_secondary,
                      e.name AS event
               FROM matches m JOIN teams t1 ON t1.team_id = m.team1_id JOIN teams t2 ON t2.team_id = m.team2_id
               JOIN events e USING (event_id)"""


def match_list(year=None, event_id=None, team_id=None):
    """Matches for the matches tab, newest first."""
    where, params = ["1"], []
    if year:
        where.append("e.year = ?")
        params.append(year)
    if event_id:
        where.append("m.event_id = ?")
        params.append(event_id)
    if team_id:
        where.append("? IN (m.team1_id, m.team2_id)")
        params.append(team_id)
    return _all(MATCH_SQL + f" WHERE {' AND '.join(where)} ORDER BY m.start_time DESC", tuple(params))


def team_options(year=None, event_id=None):
    """Teams that played in the given year/event, for the matches tab's team menu."""
    where, params = ["1"], []
    if year:
        where.append("e.year = ?")
        params.append(year)
    if event_id:
        where.append("m.event_id = ?")
        params.append(event_id)
    return _all(f"""SELECT DISTINCT t.team_id, t.name FROM matches m JOIN events e USING (event_id)
                    JOIN teams t ON t.team_id IN (m.team1_id, m.team2_id)
                    WHERE {' AND '.join(where)} ORDER BY t.name COLLATE NOCASE""", tuple(params))


def match(match_id):
    """A match with its maps, each map's rounds, and every player's stats (whole match and per map)."""
    m = _one(MATCH_SQL + " WHERE m.match_id = ?", (match_id,))
    if not m:
        return None
    m["style"] = match_style(m)
    stats = match_stats(match_id)
    m["totals"] = stats["totals"]
    rows_by_map = {mp["game_id"]: mp["rows"] for mp in stats["maps"]}
    m["maps"] = _all("SELECT * FROM maps WHERE match_id = ? ORDER BY map_number", (match_id,))
    for mp in m["maps"]:
        mp["rounds"] = _all("""SELECT round_num, winner_id, outcome, team1_score, team2_score,
                                      start_prob IS NOT NULL AS has_trace
                               FROM rounds WHERE game_id = ? ORDER BY round_num""", (mp["game_id"],))
        mp["players"] = rows_by_map.get(mp["game_id"], [])
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
    r["calc_links"] = calc_links(r, tags)

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
                          m.stage, m.event_id,
                          CASE WHEN m.team1_id = p.team_id THEN t2.tag ELSE t1.tag END AS opponent,
                          CASE WHEN m.team1_id = p.team_id THEN m.team1_score ELSE m.team2_score END AS maps_won,
                          CASE WHEN m.team1_id = p.team_id THEN m.team2_score ELSE m.team1_score END AS maps_lost,
                          CASE WHEN m.team1_id = p.team_id THEN mp.team1_score ELSE mp.team2_score END AS rounds_won,
                          CASE WHEN m.team1_id = p.team_id THEN mp.team2_score ELSE mp.team1_score END AS rounds_lost
                   FROM plays p JOIN players pl USING (player_id) JOIN teams t ON t.team_id = p.team_id
                   JOIN matches m ON m.match_id = p.match_id JOIN events e USING (event_id)
                   JOIN teams t1 ON t1.team_id = m.team1_id JOIN teams t2 ON t2.team_id = m.team2_id
                   LEFT JOIN maps mp ON mp.game_id = p.game_id
                   WHERE p.scope = ? AND p.kind = ? ORDER BY p.rank LIMIT ?""", (scope, kind, limit))
    for r in rows:
        r["credit"] = pct(r["credit"])
        r["per_round"] = r["credit"] / r["rounds"] if r["rounds"] else None
    return rows


def play_event_ids():
    """Events with best-performance lists (those with replay data)."""
    return {int(r["scope"][1:]) for r in _all("SELECT DISTINCT scope FROM plays WHERE scope LIKE 'e%'")}


def leaderboard(scope, min_rounds):
    return _all("""SELECT l.*, p.name AS player FROM leaderboard l JOIN players p USING (player_id)
                   WHERE l.scope = ? AND l.wpa_rounds >= ? ORDER BY l.shrunk DESC""", (scope, min_rounds))


# --- Stats explorer and player pages: every player's box score per map, plus WPA where there's a replay ---

ROUNDS = "(mp.team1_score + mp.team2_score)"
AGG = f"""COUNT(*) AS maps, SUM({ROUNDS}) AS rounds, SUM(pm.kills) AS kills, SUM(pm.deaths) AS deaths,
          SUM(pm.assists) AS assists,
          SUM(pm.rating * {ROUNDS}) / SUM(CASE WHEN pm.rating IS NOT NULL THEN {ROUNDS} END) AS rating,
          SUM(pm.acs * {ROUNDS}) * 1.0 / SUM(CASE WHEN pm.acs IS NOT NULL THEN {ROUNDS} END) AS acs,
          SUM(pm.wpa) AS wpa, SUM(CASE WHEN pm.wpa IS NOT NULL THEN {ROUNDS} END) AS wpa_rounds"""
FROM_PM = """FROM player_maps pm JOIN maps mp USING (game_id) JOIN matches m USING (match_id)
             JOIN events e USING (event_id)"""


def _finish(rows):
    """WPA from basis points to % of a round win, total and per round played on replay maps."""
    for r in rows:
        r["wpa"] = pct(r["wpa"])
        r["per_round"] = r["wpa"] / r["wpa_rounds"] if r.get("wpa_rounds") else None
    return rows


def player_totals(year=None, event_id=None, min_rounds=0):
    """One row per player for all years, a year or an event, with the leaderboard's shrunk WPA and range."""
    where, params = ["1"], []
    if year:
        where.append("e.year = ?")
        params.append(year)
    if event_id:
        where.append("e.event_id = ?")
        params.append(event_id)
    scope = f"e{event_id}" if event_id else (f"y{year}" if year else "all")
    rows = _all(f"""
        WITH t AS (SELECT pm.player_id, MAX(m.start_time) AS last_played, pm.team_id, {AGG}
                   {FROM_PM} WHERE {' AND '.join(where)} GROUP BY pm.player_id)
        SELECT t.*, p.name AS player, tm.tag AS team, l.shrunk, l.low, l.high
        FROM t JOIN players p USING (player_id) LEFT JOIN teams tm ON tm.team_id = t.team_id
        LEFT JOIN leaderboard l ON l.scope = ? AND l.player_id = t.player_id
        WHERE t.rounds >= ?
        ORDER BY l.shrunk IS NULL, l.shrunk DESC, t.rating DESC""", (*params, scope, min_rounds))
    return _finish(rows)


def match_stats(match_id):
    """Each player's line per map and over the whole match, grouped by team."""
    rows = _finish(_all(f"""SELECT pm.*, p.name AS player, mp.map_number, mp.map_name, mp.has_replay,
                                   {ROUNDS} AS rounds, CASE WHEN pm.wpa IS NOT NULL THEN {ROUNDS} END AS wpa_rounds
                            FROM player_maps pm JOIN maps mp USING (game_id) JOIN players p USING (player_id)
                            WHERE mp.match_id = ? ORDER BY mp.map_number""", (match_id,)))
    totals = {}
    for r in rows:
        t = totals.setdefault(r["player_id"], {"player_id": r["player_id"], "player": r["player"],
                                               "team_id": r["team_id"], "agents": [], "maps": 0, "rounds": 0,
                                               "kills": 0, "deaths": 0, "assists": 0, "wpa": None,
                                               "wpa_rounds": 0, "_rating": 0.0, "_rating_rounds": 0,
                                               "_acs": 0.0, "_acs_rounds": 0})
        t["maps"] += 1
        t["rounds"] += r["rounds"]
        for k in ("kills", "deaths", "assists"):
            t[k] += r[k] or 0
        if r["agent"] and r["agent"] not in t["agents"]:
            t["agents"].append(r["agent"])
        if r["wpa"] is not None:
            t["wpa"] = (t["wpa"] or 0) + r["wpa"]
            t["wpa_rounds"] += r["rounds"]
        if r["rating"] is not None:
            t["_rating"] += r["rating"] * r["rounds"]
            t["_rating_rounds"] += r["rounds"]
        if r["acs"] is not None:
            t["_acs"] += r["acs"] * r["rounds"]
            t["_acs_rounds"] += r["rounds"]
    for t in totals.values():
        t["rating"] = t["_rating"] / t["_rating_rounds"] if t["_rating_rounds"] else None
        t["acs"] = t["_acs"] / t["_acs_rounds"] if t["_acs_rounds"] else None
        t["per_round"] = t["wpa"] / t["wpa_rounds"] if t["wpa_rounds"] else None
    key = lambda r: (r["wpa"] is None, -(r["wpa"] or 0), -(r["rating"] or 0))
    maps = {}
    for r in rows:
        maps.setdefault(r["game_id"], {"game_id": r["game_id"], "map_number": r["map_number"],
                                       "map_name": r["map_name"], "has_replay": r["has_replay"], "rows": []})
        maps[r["game_id"]]["rows"].append(r)
    for mp in maps.values():
        mp["rows"].sort(key=key)
    return {"totals": sorted(totals.values(), key=key), "maps": list(maps.values())}


def player(player_id):
    p = _one("SELECT * FROM players WHERE player_id = ?", (player_id,))
    if not p:
        return None
    def by(col, order):
        return _finish(_all(f"SELECT {col}, {AGG} {FROM_PM} WHERE pm.player_id = ? GROUP BY {col} ORDER BY {order}",
                            (player_id,)))
    p["overall"] = _finish(_all(f"SELECT {AGG} {FROM_PM} WHERE pm.player_id = ?", (player_id,)))[0]
    p["years"] = by("e.year", "e.year DESC")
    p["events"] = by("e.event_id", "MIN(m.start_time) DESC")
    names = {e["event_id"]: e for e in _all("SELECT event_id, name, year FROM events")}
    for e in p["events"]:
        e.update(names[e["event_id"]])
    p["matches"] = _finish(_all(f"""
        SELECT m.match_id, m.event_id, m.start_time, m.stage, e.name AS event, pm.team_id,
               CASE WHEN m.team1_id = pm.team_id THEN t2.tag ELSE t1.tag END AS opponent,
               CASE WHEN m.team1_id = pm.team_id THEN m.team1_score ELSE m.team2_score END AS maps_won,
               CASE WHEN m.team1_id = pm.team_id THEN m.team2_score ELSE m.team1_score END AS maps_lost,
               tm.tag AS team, {AGG}
        {FROM_PM} JOIN teams t1 ON t1.team_id = m.team1_id JOIN teams t2 ON t2.team_id = m.team2_id
        JOIN teams tm ON tm.team_id = pm.team_id
        WHERE pm.player_id = ? GROUP BY m.match_id ORDER BY m.start_time DESC""", (player_id,)))
    return p


def event_options():
    return _all("SELECT event_id, name, year FROM events ORDER BY first_match DESC")


# Force-buy calculator (table calc, from vct-ratings' python/economy/precompute.py).
CALC_OPTIONS = ["eco", "half", "force", "full", "bonus"]
CALC_STATS = ["map", "round", "if_win", "if_lose"]


def calc_meta():
    """The calculator grid's settings, or None if this data file has no calculator grid."""
    if not _one("SELECT 1 FROM sqlite_master WHERE name = 'calc'"):
        return None
    return {r["key"]: r["value"] for r in _all("SELECT key, value FROM calc_meta")}


CARRY_EDGES = (1000, 6000)  # guns kept, as in precompute.py's CARRY_BINS: none / 1-2 guns / 3+ guns
BUY_NAMES = {"eco": "a save", "half": "a half buy", "force": "a force", "full": "a full buy", "bonus": "a bonus buy"}


def _carry_bin(credits):
    return sum(credits > edge for edge in CARRY_EDGES)


def calc_links(r, tags):
    """For a round the calculator covers: each team's spot as calculator query strings, with what it bought."""
    round_num = r["round_num"]
    if not 2 <= round_num <= 24 or round_num == 13 or not calc_meta():
        return []
    try:
        econ = {e["team_id"]: e for e in _all("SELECT * FROM round_econ WHERE game_id = ? AND round_num = ?",
                                              (r["game_id"], round_num))}
    except sqlite3.OperationalError:  # a data file from before round_econ
        return []
    if len(econ) != 2 or any(e["buy"] not in BUY_NAMES for e in econ.values()):
        return []
    wins = {w["winner_id"]: w["n"] for w in _all(
        "SELECT winner_id, COUNT(*) AS n FROM rounds WHERE game_id = ? AND round_num < ? GROUP BY winner_id",
        (r["game_id"], round_num))}
    links = []
    for team, opp in ((r["attacker_id"], r["defender_id"]), (r["defender_id"], r["attacker_id"])):
        me, them = econ[team], econ[opp]
        last = min(them["loss_streak"], 3) if me["loss_streak"] == 0 else -min(me["loss_streak"], 3)
        query = {"round": round_num, "score": wins.get(team, 0), "side": "atk" if team == r["attacker_id"] else "def",
                 "last": last, "carry": _carry_bin(me["carried_in"]), "opp_carry": _carry_bin(them["carried_in"]),
                 "bank": me["bank"], "opp": them["bank"], "actual": me["buy"]}
        links.append({"tag": tags[team], "query": urlencode(query), "bank": f"{me['bank']:,}",
                      "bought": BUY_NAMES[me["buy"]]})
    return links


def calc_cells(round_num, score, side, last, carry, opp_carry):
    """Every precomputed money situation for one round, score, side, last result and guns kept (bins 0-2 for
    each team), as compact rows:
    [bank, opp_bank, then map / round / if_win / if_lose in percent for each of CALC_OPTIONS (None if the
    option isn't possible there)]."""
    cols = [f"{o}_{s}" for o in CALC_OPTIONS for s in CALC_STATS]
    rows = _all(f"SELECT bank, opp_bank, {', '.join(cols)} FROM calc "
                "WHERE round_num = ? AND score = ? AND side = ? AND last = ? AND carry = ? AND opp_carry = ?",
                (round_num, score, side, last, carry, opp_carry))
    return [[r["bank"], r["opp_bank"]] + [pct(r[c]) for c in cols] for r in rows]
