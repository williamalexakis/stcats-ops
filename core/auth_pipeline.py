# Copyright © William Alexakis. All Rights Reserved. Use governed by LICENSE file.

from typing import Any, Dict, Optional

from django import forms
from django.urls import reverse
from social_core.pipeline.partial import partial

from .forms import SSOSignupForm


@partial
def require_invite(strategy, backend, user=None, *args, **kwargs):

    """Ensure invite data is collected before creating a new SSO user."""

    if user:

        return {}

    session_data: Optional[Dict[str, Any]] = strategy.session_get("sso_signup_data")

    if session_data:

        return {"sso_signup_data": session_data}

    return strategy.redirect(reverse("complete_sso_signup"))


def create_user_from_microsoft(
    strategy,
    backend,
    details,
    user=None,
    sso_signup_data: Optional[Dict[str, Any]] = None,
    *args,
    **kwargs
):

    """Create a Django user from Microsoft account details."""

    if user:

        return {"user": user}

    if not sso_signup_data:

        return strategy.redirect(reverse("complete_sso_signup"))

    form = SSOSignupForm(data=sso_signup_data)

    if not form.is_valid():

        strategy.session_set("sso_signup_errors", form.errors.get_json_data())
        strategy.session_set("sso_signup_data", sso_signup_data)

        return strategy.redirect(reverse("complete_sso_signup"))

    email = (details.get("email") or details.get("preferred_username") or "").lower()

    extra_fields = {}

    first_name = details.get("first_name") or details.get("given_name")
    last_name = details.get("last_name") or details.get("family_name")

    if first_name:

        extra_fields["first_name"] = first_name

    if last_name:

        extra_fields["last_name"] = last_name

    try:

        new_user = form.save(email=email, extra_fields=extra_fields)

    except forms.ValidationError as error:

        strategy.session_set(
            "sso_signup_errors",
            {"invite_code": [{"message": msg, "code": "invalid"} for msg in error.messages]}
        )
        strategy.session_set("sso_signup_data", sso_signup_data)

        return strategy.redirect(reverse("complete_sso_signup"))

    strategy.session_pop("sso_signup_data")
    strategy.session_pop("sso_signup_errors")
    strategy.session_pop("partial_pipeline_token")

    return {"user": new_user}
