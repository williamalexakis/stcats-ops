from django.http import HttpResponse
from django.shortcuts import render

def home(request):

    return render(request, "core/home.html")

def healthcheck(request):

    return HttpResponse("OK", content_type="text/plain")

# TODO: Unplaceholder this placeholder
def rooms(request):

    pass
