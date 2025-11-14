/* Copyright © William Alexakis. All Rights Reserved. Use governed by LICENSE file. */

(function () {
    const sidecard = document.getElementById('member-sidecard');
    if (!sidecard) {
        return;
    }

    const fields = {
        name: sidecard.querySelector('[data-member-field="name"]'),
        role: sidecard.querySelector('[data-member-field="role"]'),
        email: sidecard.querySelector('[data-member-field="email"]'),
        initial: sidecard.querySelector('[data-member-field="initial"]'),
        displayName: sidecard.querySelector('[data-member-field="display-name"]')
    };
    const displaySection = sidecard.querySelector('[data-member-display-section]');
    const displayForm = sidecard.querySelector('[data-member-display-form]');
    const displayInput = displayForm ? displayForm.querySelector('input[name="display_name"]') : null;
    const displayFeedback = sidecard.querySelector('[data-member-display-feedback]');
    let activeTrigger = null;

    function setInitial(name, scheme) {
        if (!fields.initial) {
            return;
        }

        const initial = name ? name.trim().charAt(0).toUpperCase() : '';
        fields.initial.textContent = initial || '?';
        fields.initial.classList.remove('member-card__avatar--admin', 'member-card__avatar--teacher');

        if (scheme === 'admin') {
            fields.initial.classList.add('member-card__avatar--admin');
        } else {
            fields.initial.classList.add('member-card__avatar--teacher');
        }
    }

    function setEmail(email) {
        if (!fields.email) {
            return;
        }

        const value = email && email !== 'N/A' ? email : 'N/A';
        fields.email.textContent = value;

        if (value !== 'N/A') {
            fields.email.setAttribute('href', `mailto:${value}`);
        } else {
            fields.email.removeAttribute('href');
        }
    }

    function setDisplayName(value) {
        if (!fields.displayName) {
            return;
        }

        fields.displayName.textContent = value || 'N/A';
    }

    function toggleDisplayForm(canEdit, value) {
        if (displayInput) {
            displayInput.value = value || '';
        }

        if (displaySection) {
            displaySection.setAttribute('data-member-display-mode', canEdit ? 'edit' : 'view');
        }

        setDisplayFeedback('');
    }

    function setDisplayFeedback(message, isSuccess = false) {
        if (!displayFeedback) {
            return;
        }

        displayFeedback.textContent = message || '';
        displayFeedback.classList.remove('member-sidecard__feedback--success', 'member-sidecard__feedback--error');

        if (!message) {
            return;
        }

        displayFeedback.classList.add(isSuccess ? 'member-sidecard__feedback--success' : 'member-sidecard__feedback--error');
    }

    function openSidecard(trigger) {
        activeTrigger = trigger;
        const username = trigger.dataset.memberUsername || 'N/A';
        const role = trigger.dataset.memberRole || 'N/A';
        const email = trigger.dataset.memberEmail || 'N/A';
        const scheme = trigger.dataset.memberRoleScheme === 'admin' ? 'admin' : 'teacher';
        const displayName = trigger.dataset.memberDisplayName || '';
        const canEdit = trigger.dataset.memberCanEdit === 'true';

        if (fields.name) {
            fields.name.textContent = username;
        }

        if (fields.role) {
            fields.role.textContent = role;
        }

        setInitial(displayName || username, scheme);
        setEmail(email);
        setDisplayName(displayName);
        toggleDisplayForm(canEdit, displayName);

        sidecard.removeAttribute('hidden');
        sidecard.setAttribute('aria-hidden', 'false');
        document.body.classList.add('sidecard-open');
        window.requestAnimationFrame(() => {
            sidecard.classList.add('entry-sidecard--open');
        });

        document.querySelectorAll('[data-member-info]').forEach((button) => {
            button.setAttribute('aria-expanded', button === trigger ? 'true' : 'false');
        });
    }

    function closeSidecard() {
        if (sidecard.classList.contains('entry-sidecard--open')) {
            sidecard.classList.remove('entry-sidecard--open');
            sidecard.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('sidecard-open');
            window.setTimeout(() => sidecard.setAttribute('hidden', ''), 220);
        }

        document.querySelectorAll('[data-member-info]').forEach((button) => {
            button.setAttribute('aria-expanded', 'false');
        });

        activeTrigger = null;
    }

    function updateTriggerDatasets(username, displayName) {
        document.querySelectorAll(`[data-member-info][data-member-username="${username}"]`).forEach((button) => {
            button.dataset.memberDisplayName = displayName;
        });

        document.querySelectorAll(`[data-member-name-label="${username}"]`).forEach((node) => {
            node.textContent = displayName || username;
        });

        document.querySelectorAll(`[data-member-avatar-label="${username}"]`).forEach((node) => {
            const initial = (displayName || username || '?').trim().charAt(0).toUpperCase() || '?';
            node.textContent = initial;
        });
    }

    async function handleDisplaySubmit(event) {
        event.preventDefault();

        if (!displayForm || !displayInput || !activeTrigger) {
            return;
        }

        const submitButton = displayForm.querySelector('button[type="submit"]');
        const formData = new FormData(displayForm);
        setDisplayFeedback('');

        if (submitButton) {
            submitButton.disabled = true;
        }

        try {
            const response = await fetch(displayForm.action, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            });

            const payload = await response.json();

            if (!response.ok || !payload || !payload.success) {
                throw new Error((payload && payload.message) || 'Unable to update display name.');
            }

            const normalized = payload.display_name || '';
            setDisplayName(normalized);
            displayInput.value = normalized;
            setDisplayFeedback('Display name updated.', true);
            const username = activeTrigger.dataset.memberUsername || '';
            updateTriggerDatasets(username, normalized);
            const scheme = activeTrigger.dataset.memberRoleScheme === 'admin' ? 'admin' : 'teacher';
            setInitial(normalized || username, scheme);
        } catch (error) {
            setDisplayFeedback(error.message || 'Unable to update display name.', false);
        } finally {
            if (submitButton) {
                submitButton.disabled = false;
            }
        }
    }

    document.addEventListener('click', (event) => {
        if (event.target.closest('[data-member-sidecard-dismiss]')) {
            closeSidecard();
            return;
        }

        const trigger = event.target.closest('[data-member-info]');
        if (!trigger) {
            return;
        }

        event.preventDefault();
        openSidecard(trigger);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeSidecard();
        }
    });

    if (displayForm) {
        displayForm.addEventListener('submit', handleDisplaySubmit);
    }
})();
