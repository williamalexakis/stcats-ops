from django import forms
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth import login, logout
from django.http import HttpRequest, HttpResponse
from .forms import SignupForm

def signup(request: HttpRequest) -> HttpResponse:

    """Handle account creation via invite and log the user in."""

    if request.method == "POST":

        form = SignupForm(request.POST)

        if form.is_valid():

            try:

                user = form.save()

            except forms.ValidationError as error:

                form.add_error("invite_code", error)

            else:

                messages.success(request, "Account successfully created!")
                login(request, user)

                return redirect(reverse("home"))

    else:

        form = SignupForm()

    return render(request, "core/signup.html", {"form": form})

def logout_view(request: HttpRequest) -> HttpResponse:

    """Log the current user out and redirect to the login page."""

    logout(request)
    messages.success(request, "You have been successfully logged out.")

    return redirect(reverse("login"))
