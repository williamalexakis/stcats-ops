# Copyright © William Alexakis. All Rights Reserved. Use governed by LICENSE file.

import json
from typing import Any, Dict

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from social_django.utils import load_strategy

from .forms import SignupForm, SSOSignupForm

def signup(request: HttpRequest) -> HttpResponse:

    """Display the Microsoft SSO entry point for new account creation."""

    azure_configured = all([
        settings.SOCIAL_AUTH_AZUREAD_OAUTH2_KEY,
        settings.SOCIAL_AUTH_AZUREAD_OAUTH2_SECRET,
        settings.SOCIAL_AUTH_AZUREAD_OAUTH2_TENANT_ID
    ])

    return render(
        request,
        "core/signup.html",
        {
            "azure_configured": azure_configured,
            "legacy_signup_url": reverse("legacy_signup"),
        }
    )

def complete_sso_signup(request: HttpRequest) -> HttpResponse:

    """Collect username and invite code after Microsoft authentication."""

    strategy = load_strategy(request)
    partial_token = request.GET.get("partial_token") or request.POST.get("partial_token")

    if not partial_token:

        partial_token = strategy.session_get("partial_pipeline_token")

    if not partial_token:

        messages.error(request, "Your Microsoft login session has expired. Please start the signup again.")

        return redirect(reverse("signup"))

    partial = strategy.partial_load(partial_token)

    if partial is None:

        messages.error(request, "Unable to resume Microsoft signup. Please try again.")

        return redirect(reverse("signup"))

    strategy.session_set("partial_pipeline_token", partial_token)

    stored_data: Dict[str, Any] = strategy.session_get("sso_signup_data") or {}
    stored_errors_raw = strategy.session_get("sso_signup_errors")
    strategy.session_pop("sso_signup_errors")

    if isinstance(stored_errors_raw, str):

        try:

            stored_errors = json.loads(stored_errors_raw)

        except json.JSONDecodeError:

            stored_errors = None

    else:

        stored_errors = stored_errors_raw

    if request.method == "POST":

        form = SSOSignupForm(request.POST)

        if form.is_valid():

            strategy.session_set("sso_signup_data", form.cleaned_data)
            complete_url = reverse("social:complete", args=[partial.backend])

            return redirect(f"{complete_url}?partial_token={partial_token}")

    else:

        if stored_errors:

            form = SSOSignupForm(data=stored_data or None)

        elif stored_data:

            form = SSOSignupForm(initial=stored_data)

        else:

            form = SSOSignupForm()

        if stored_errors:

            for field, field_errors in stored_errors.items():

                for error in field_errors:

                    message_text = error.get("message")

                    if not message_text:

                        continue

                    if field == "__all__":

                        form.add_error(None, message_text)

                    else:

                        form.add_error(field, message_text)

    microsoft_details = partial.data.get("kwargs", {}).get("details", {})
    microsoft_email = (
        microsoft_details.get("email")
        or microsoft_details.get("preferred_username")
        or ""
    )

    return render(
        request,
        "core/sso_signup.html",
        {
            "form": form,
            "partial_token": partial_token,
            "microsoft_email": microsoft_email,
        }
    )

def legacy_signup(request: HttpRequest) -> HttpResponse:

    """Handle account creation via invite for the legacy username/password flow."""

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

    return render(request, "core/legacy_signup.html", {"form": form})

def logout_view(request: HttpRequest) -> HttpResponse:

    """Log the current user out and redirect to the login page."""

    logout(request)
    messages.success(request, "You have been successfully logged out.")

    return redirect(reverse("login"))
