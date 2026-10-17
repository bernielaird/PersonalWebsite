from django.urls import path

from . import views

app_name = "vct"

urlpatterns = [
    path("", views.index, name="index"),
    path("event/<int:event_id>/", views.event, name="event"),
    path("match/<int:match_id>/", views.match, name="match"),
    path("round/<int:game_id>/<int:round_num>/", views.round_view, name="round"),
    path("plays/", views.plays, name="plays"),
    path("players/", views.players, name="players"),
]
