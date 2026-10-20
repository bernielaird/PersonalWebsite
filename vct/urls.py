from django.urls import path

from . import views

app_name = "vct"

urlpatterns = [
    path("", views.index, name="index"),
    path("event/<int:event_id>/", views.event, name="event"),
    path("matches/", views.matches, name="matches"),
    path("match/<int:match_id>/", views.match, name="match"),
    path("round/<int:game_id>/<int:round_num>/", views.round_view, name="round"),
    path("plays/", views.plays, name="plays"),
    path("stats/", views.stats, name="stats"),
    path("players/", views.players, name="players"),
    path("player/<int:player_id>/", views.player, name="player"),
    path("calculator/", views.calculator, name="calculator"),
    path("calculator/data/", views.calculator_data, name="calculator_data"),
]
