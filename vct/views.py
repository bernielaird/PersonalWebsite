from itertools import groupby

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from . import data

FEATURED_ROUND = (280042, 23)  # Americas Stage 2 grand final, map 5 (Haven), round 23
GITHUB = "https://github.com/bernielaird/vctstats"
MIN_ROUNDS = {"all": 0, "y": 0, "e": 0}  # default stats cut-off by scope type


def _render(request, template, context):
    context.setdefault("github", GITHUB)
    return render(request, f"vct/{template}", context)


def _by_year(events):
    return [(y, list(es)) for y, es in groupby(sorted(events, key=lambda e: -e["year"]), key=lambda e: e["year"])]


def index(request):
    meta = {k: f"{int(v):,}" if v.isdigit() else v for k, v in data.meta().items()}
    years = data.years()
    return _render(request, "index.html", {
        "meta": meta,
        "first_year": years[0], "last_year": years[-1],
        "events_by_year": _by_year(data.events()),
        "featured": FEATURED_ROUND,
    })


def event(request, event_id):
    e = data.event(event_id)
    if not e:
        raise Http404("No such event")
    return _render(request, "event.html", {"event": e, "matches": data.event_matches(event_id)})


def match(request, match_id):
    m = data.match(match_id)
    if not m:
        raise Http404("No such match")
    return _render(request, "match.html", {"match": m})


def round_view(request, game_id, round_num):
    r = data.round_detail(game_id, round_num)
    if not r:
        raise Http404("No such round")
    return _render(request, "round.html", {"r": r})


PLAY_TABS = [("round", "rounds"), ("map", "maps"), ("match", "matches")]


def plays(request):
    """Best rounds, maps and matches for all years, a year or one tournament."""
    years = data.years()
    with_plays = data.play_event_ids()
    events = [e for e in data.event_options() if e["event_id"] in with_plays]
    kind = request.GET.get("view", "round")
    if kind not in dict(PLAY_TABS):
        kind = "round"
    year = _int(request.GET.get("year"))
    year = year if year in years else None
    event = next((e for e in events if e["event_id"] == _int(request.GET.get("event"))), None)
    if event and year and event["year"] != year:
        event = None
    if event:
        year = event["year"]
    scope = f"e{event['event_id']}" if event else (f"y{year}" if year else "all")
    title = event["name"] if event else (str(year) if year else f"All years ({years[0]}–{years[-1]})")
    return _render(request, "plays.html", {
        "tabs": PLAY_TABS, "kind": kind, "years": list(reversed(years)), "year": year, "event": event,
        "events": [e for e in events if not year or e["year"] == year], "title": title,
        "rows": data.plays(scope, kind, 100),
    })


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def stats(request):
    """Every player's numbers for all years, a year, a tournament or one match (drill down with the menus)."""
    years = data.years()
    events = data.event_options()
    year = _int(request.GET.get("year"))
    year = year if year in years else None
    event = next((e for e in events if e["event_id"] == _int(request.GET.get("event"))), None)
    if event and year and event["year"] != year:
        event = None
    if event:
        year = event["year"]
    matches = data.event_matches(event["event_id"]) if event else []
    match = next((m for m in matches if m["match_id"] == _int(request.GET.get("match"))), None)

    context = {"years": list(reversed(years)), "year": year, "event": event, "match": match,
               "events": [e for e in events if not year or e["year"] == year], "matches": matches}
    if match:
        context["match_stats"] = data.match_stats(match["match_id"])
        context["title"] = f"{match['team1']} vs {match['team2']}"
    else:
        default_min = MIN_ROUNDS["e" if event else ("y" if year else "all")]
        min_rounds = _int(request.GET.get("min"))
        min_rounds = default_min if min_rounds is None or min_rounds < 0 else min_rounds
        context.update(min_rounds=min_rounds,
                       rows=data.player_totals(year, event and event["event_id"], min_rounds),
                       title=event["name"] if event else (str(year) if year else f"All years ({years[0]}–{years[-1]})"))
    return _render(request, "stats.html", context)


def players(request):
    """Old leaderboard URL (?scope=all|y2026|e123): send to the stats page."""
    scope = request.GET.get("scope", "all")
    query = {"y": "year", "e": "event"}.get(scope[:1])
    target = reverse("vct:stats") + (f"?{query}={scope[1:]}" if query and scope[1:].isdigit() else "")
    return redirect(target)


def player(request, player_id):
    p = data.player(player_id)
    if not p:
        raise Http404("No such player")
    return _render(request, "player.html", {"p": p})
