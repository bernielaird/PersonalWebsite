from itertools import groupby

from django.http import Http404
from django.shortcuts import render

from . import data

FEATURED_ROUND = (280042, 23)  # Americas Stage 2 grand final, map 5 (Haven), round 23
GITHUB = "https://github.com/bernielaird/vctstats"
MIN_ROUNDS = {"all": 2000, "y": 600, "e": 300}  # default leaderboard cut-off by scope type


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
    return _render(request, "event.html", {"event": e, "matches": data.event_matches(event_id),
                                           "has_wpa": bool(data.leaderboard(f"e{event_id}", 0)[:1])})


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


PLAY_TABS = [("round", "rounds"), ("kill", "kills"), ("map", "maps"), ("match", "matches")]


def plays(request):
    scopes = data.scopes()
    kind = request.GET.get("view", "round")
    if kind not in dict(PLAY_TABS):
        kind = "round"
    scope = request.GET.get("scope", "all")
    if scope not in dict(scopes):
        scope = "all"
    return _render(request, "plays.html", {
        "tabs": PLAY_TABS, "kind": kind, "scopes": scopes, "scope": scope, "scope_name": dict(scopes)[scope],
        "rows": data.plays(scope, kind, 100),
    })


def players(request):
    scopes = data.scopes()
    events = [e | {"scope": f"e{e['event_id']}"} for e in data.events() if e["has_wpa"]]
    names = dict(scopes) | {e["scope"]: e["name"] for e in events}
    scope = request.GET.get("scope", "all")
    if scope not in names:
        scope = "all"
    default_min = MIN_ROUNDS[scope if scope == "all" else scope[0]]
    try:
        min_rounds = max(0, int(request.GET.get("min", default_min)))
    except ValueError:
        min_rounds = default_min
    return _render(request, "players.html", {
        "scopes": scopes, "events_by_year": _by_year(events), "scope": scope, "scope_name": names[scope],
        "min_rounds": min_rounds, "rows": data.leaderboard(scope, min_rounds),
    })
