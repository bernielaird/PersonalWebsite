from itertools import groupby

from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import cache_control

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


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _year_event(request, events, years):
    """The ?year= and ?event= filters, validated. An event implies its year; a mismatched pair drops the event."""
    year = _int(request.GET.get("year"))
    year = year if year in years else None
    event = next((e for e in events if e["event_id"] == _int(request.GET.get("event"))), None)
    if event and year and event["year"] != year:
        event = None
    if event:
        year = event["year"]
    return year, event


def _title(year, event, years):
    return event["name"] if event else (str(year) if year else f"All years ({years[0]}–{years[-1]})")


def event(request, event_id):
    """Old event page: the matches tab, filtered to that event."""
    if not data.event(event_id):
        raise Http404("No such event")
    return redirect(reverse("vct:matches") + f"?event={event_id}")


def matches(request):
    """Browse matches by year, tournament and team. Defaults to the latest year."""
    years = data.years()
    events = data.event_options()
    if not request.GET:
        return redirect(reverse("vct:matches") + f"?year={years[-1]}")
    year, event = _year_event(request, events, years)
    teams = data.team_options(year, event and event["event_id"])
    team = next((t for t in teams if t["team_id"] == _int(request.GET.get("team"))), None)
    title = _title(year, event, years) + (f": {team['name']}" if team else "")
    return _render(request, "matches.html", {
        "years": list(reversed(years)), "year": year, "event": event, "team": team, "teams": teams,
        "events": [e for e in events if not year or e["year"] == year], "title": title,
        "matches": data.match_list(year, event and event["event_id"], team and team["team_id"]),
    })


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
    year, event = _year_event(request, events, years)
    scope = f"e{event['event_id']}" if event else (f"y{year}" if year else "all")
    title = _title(year, event, years)
    return _render(request, "plays.html", {
        "tabs": PLAY_TABS, "kind": kind, "years": list(reversed(years)), "year": year, "event": event,
        "events": [e for e in events if not year or e["year"] == year], "title": title,
        "rows": data.plays(scope, kind, 100),
    })


def stats(request):
    """Every player's numbers for all years, a year or a tournament."""
    match_id = _int(request.GET.get("match"))
    if match_id:  # old links to a single match: that's the match page now
        return redirect("vct:match", match_id=match_id)
    years = data.years()
    events = data.event_options()
    year, event = _year_event(request, events, years)
    default_min = MIN_ROUNDS["e" if event else ("y" if year else "all")]
    min_rounds = _int(request.GET.get("min"))
    min_rounds = default_min if min_rounds is None or min_rounds < 0 else min_rounds
    return _render(request, "stats.html", {
        "years": list(reversed(years)), "year": year, "event": event,
        "events": [e for e in events if not year or e["year"] == year],
        "min_rounds": min_rounds, "rows": data.player_totals(year, event and event["event_id"], min_rounds),
        "title": _title(year, event, years),
    })


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


def calculator(request):
    """Force-buy calculator: the page; the odds come from calculator_data as you change the inputs."""
    meta = data.calc_meta()
    return _render(request, "calculator.html", {
        "meta": meta,
        "options": data.CALC_OPTIONS, "stats": data.CALC_STATS,
        "levels": [int(x) for x in meta["bank_levels"].split(",")] if meta else [],
        "rounds": [r for r in range(2, 25) if r != 13],
    })


@cache_control(public=True, max_age=86400)
def calculator_data(request):
    """The precomputed money grid for one round, score, side and last result (JSON)."""
    round_num, score = _int(request.GET.get("round")), _int(request.GET.get("score"))
    last, side = _int(request.GET.get("last")), request.GET.get("side")
    if round_num is None or score is None or last is None or side not in ("atk", "def") or not data.calc_meta():
        raise Http404("Bad calculator query")
    return JsonResponse({"cells": data.calc_cells(round_num, score, side, last)})
