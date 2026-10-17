from django import template

register = template.Library()


@register.filter
def signed(value, digits=1):
    """+21.4 / −19.4 (true minus sign); blank for None."""
    if value is None:
        return ""
    s = f"{abs(value):.{int(digits)}f}"
    if float(s) == 0:
        return s
    return ("+" if value > 0 else "−") + s


@register.filter
def pct(value, digits=1):
    return "" if value is None else f"{value:.{int(digits)}f}%"
