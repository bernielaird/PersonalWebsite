from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("about/", views.about, name="about"),
    path("projects/", views.projects, name="projects"),
    path("projects/transit/", views.transit, name="transit"),
    path("projects/transit/demo/", views.transit_demo, name="transit_demo"),
    path("contact/", views.contact, name="contact")

]