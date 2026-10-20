from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin

# Create your views here.
def index(request):
    return render(request, "mainsite/index.html")

def about(request):
    return render(request, "mainsite/about.html")

def projects(request):
    return render(request, "mainsite/projects.html")

def contact(request):
    return render(request, "mainsite/contact.html")

def transit(request):
    return render(request, "mainsite/transit.html")

@xframe_options_sameorigin  # shown in an iframe on the transit page
def transit_demo(request):
    return render(request, "mainsite/transit_demo.html")