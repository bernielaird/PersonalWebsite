from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def index(request):
    return render(request, "mainsite/index.html")

def about(request):
    return render(request, "mainsite/about.html")

def projects(request):
    return render(request, "mainsite/projects.html")

def contact(request):
    return render(request, "mainsite/contact.html")