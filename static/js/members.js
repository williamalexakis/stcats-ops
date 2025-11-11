/* Copyright © William Alexakis. All Rights Reserved. Use governed by LICENSE file. */

(function () {
    const sidecard = document.getElementById('member-sidecard');
    if (!sidecard) {
        return;
    }

    const overlay = sidecard.querySelector('[data-member-sidecard-dismiss]');
    const fields = {
        name: sidecard.querySelector('[data-member-field="name"]'),
        role: sidecard.querySelector('[data-member-field="role"]'),
        email: sidecard.querySelector('[data-member-field="email"]'),
        initial: sidecard.querySelector('[data-member-field="initial"]')
    };

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

    function openSidecard(trigger) {
        const username = trigger.dataset.memberUsername || 'N/A';
        const role = trigger.dataset.memberRole || 'N/A';
        const email = trigger.dataset.memberEmail || 'N/A';
        const scheme = trigger.dataset.memberRoleScheme === 'admin' ? 'admin' : 'teacher';

        if (fields.name) {
            fields.name.textContent = username;
        }

        if (fields.role) {
            fields.role.textContent = role;
        }

        setInitial(username, scheme);
        setEmail(email);

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
})();
