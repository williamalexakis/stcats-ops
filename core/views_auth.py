from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth import login
from .forms import SignupForm


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)

        if form.is_valid():
            user = form.save()
            messages.success(request, "Account successfully created!")
            login(request, user)

            return redirect(reverse("home"))
    else:
        form = SignupForm()

    return render(request, "core/signup.html", {"form": form})
