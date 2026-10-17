"""Team colors for a match: which color each side gets, and readable text versions for both themes.

Colors come from the teams table (primary_color, secondary_color; from vct-ratings' team_colors.csv).
"""
import colorsys

DEFAULT_1, DEFAULT_2 = "#cf6d1d", "#4077d1"  # the site's orange and blue, for teams without colors
NEUTRAL = "#6b6b70"                          # for teams whose colors are only black/white/grey
BG_LIGHT, BG_DARK = "#f5f5f5", "#16161a"     # the page backgrounds (styles.css --bg)


def _rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#" + "".join(f"{round(max(0, min(255, v))):02x}" for v in rgb)


def _luminance(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in _rgb(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _mix(c, toward, t):
    return _hex(tuple(a + (b - a) * t for a, b in zip(_rgb(c), _rgb(toward))))


def _neutral(c):
    """Black, white or grey: invisible on one of the two themes, and says nothing about the team."""
    _, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in _rgb(c)))
    return s < 0.18 or v < 0.12


def _distance(a, b):
    (r1, g1, b1), (r2, g2, b2) = _rgb(a), _rgb(b)
    rm = (r1 + r2) / 2  # "redmean" approximation of how different two colors look
    return ((2 + rm / 256) * (r1 - r2) ** 2 + 4 * (g1 - g2) ** 2 + (2 + (255 - rm) / 256) * (b1 - b2) ** 2) ** 0.5


def _candidates(primary, secondary):
    return [c for c in (primary, secondary) if c and not _neutral(c)]


def _readable(c, bg, toward):
    """c, moved toward black or white just until it has 3:1 contrast with the background."""
    for i in range(11):
        mixed = _mix(c, toward, i / 10)
        if _contrast(mixed, bg) >= 3:
            return mixed
    return toward


def pick(t1_primary, t1_secondary, t2_primary, t2_secondary):
    """(team1 color, team2 color), using secondaries when a primary is neutral or the two clash."""
    c1s = _candidates(t1_primary, t1_secondary) or ([NEUTRAL] if t1_primary else [DEFAULT_1])
    c2s = _candidates(t2_primary, t2_secondary) or ([NEUTRAL] if t2_primary else [DEFAULT_2])
    for c1, c2 in ((c1s[0], c2s[0]), *((c1s[0], c) for c in c2s[1:]), *((c, c2s[0]) for c in c1s[1:])):
        if _distance(c1, c2) >= 150:
            return c1, c2
    c1 = c1s[0]
    return c1, (DEFAULT_2 if _distance(c1, DEFAULT_2) >= _distance(c1, DEFAULT_1) else DEFAULT_1)


def match_style(m):
    """CSS variables for a match dict (from data.MATCH_SQL), for a style="" attribute."""
    c1, c2 = pick(m.get("team1_primary"), m.get("team1_secondary"), m.get("team2_primary"), m.get("team2_secondary"))
    out = []
    for n, c in ((1, c1), (2, c2)):
        on = "#ffffff" if _contrast(c, "#ffffff") >= _contrast(c, "#111111") else "#111111"
        out += [f"--team{n}: {c}", f"--team{n}-on: {on}",
                f"--team{n}-l: {_readable(c, BG_LIGHT, '#000000')}", f"--team{n}-d: {_readable(c, BG_DARK, '#ffffff')}"]
    return "; ".join(out)
