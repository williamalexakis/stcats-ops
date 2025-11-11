/* Copyright © William Alexakis. All Rights Reserved. Use governed by LICENSE file. */

(function () {
    let sidecard = null;
    let noteForm = null;
    let noteField = null;
    let entryIdInput = null;
    let feedbackNode = null;
    let saveButton = null;
    let statusPill = null;
    let statusLabel = null;
    let currentEntry = null;
    let closeTimer = null;
    let bindingsRegistered = false;

    const fieldNodes = {};
    const sectionNodes = {};

    function hydrateSidecard() {
        sidecard = document.getElementById('entry-sidecard');

        if (!sidecard) {
            return false;
        }

        noteForm = sidecard.querySelector('[data-sidecard-note-form]');
        noteField = noteForm ? noteForm.querySelector('textarea[name="note"]') : null;
        entryIdInput = noteForm ? noteForm.querySelector('input[name="entry_id"]') : null;
        feedbackNode = sidecard.querySelector('[data-sidecard-feedback]');
        saveButton = sidecard.querySelector('[data-sidecard-save]');
        statusPill = sidecard.querySelector('[data-sidecard-status]');
        statusLabel = sidecard.querySelector('[data-sidecard-field="status-label"]');

        fieldNodes.subject = sidecard.querySelector('[data-sidecard-field="subject"]');
        fieldNodes.date = sidecard.querySelector('[data-sidecard-field="date"]');
        fieldNodes.teacher = sidecard.querySelector('[data-sidecard-field="teacher"]');
        fieldNodes.teacherInitial = sidecard.querySelector('[data-sidecard-field="teacher-initial"]');
        fieldNodes.time = sidecard.querySelector('[data-sidecard-field="time"]');
        fieldNodes.badgeSubject = sidecard.querySelector('[data-sidecard-field="badge-subject"]');
        fieldNodes.badgeClassroom = sidecard.querySelector('[data-sidecard-field="badge-classroom"]');
        fieldNodes.badgeCourse = sidecard.querySelector('[data-sidecard-field="badge-course"]');
        fieldNodes.badgeGroup = sidecard.querySelector('[data-sidecard-field="badge-group"]');
        fieldNodes.series = sidecard.querySelector('[data-sidecard-field="series"]');

        sectionNodes.group = sidecard.querySelector('[data-sidecard-section="group"]');
        sectionNodes.recurrence = sidecard.querySelector('[data-sidecard-section="recurrence"]');

        return Boolean(noteForm && noteField && entryIdInput && statusPill && statusLabel);
    }

    function ensureBindings() {
        if (bindingsRegistered || !sidecard) {
            return;
        }

        document.addEventListener('click', handleEntryClick);
        document.addEventListener('keydown', handleEscapeKey);

        bindingsRegistered = true;
    }

    function bindNoteForm() {
        if (noteForm && !noteForm.dataset.bound) {
            noteForm.addEventListener('submit', handleNoteSubmit);
            noteForm.dataset.bound = 'true';
        }
    }

    function bindSidecardDismiss() {
        if (sidecard && !sidecard.dataset.dismissBound) {
            sidecard.addEventListener('click', handleDismissClick);
            sidecard.dataset.dismissBound = 'true';
        }
    }

    function handleEntryClick(event) {
        const trigger = event.target.closest('[data-entry-trigger]');
        if (!trigger) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        openSidecard(trigger);
    }

    function handleDismissClick(event) {
        if (event.target.closest('[data-sidecard-dismiss]')) {
            closeSidecard();
        }
    }

    function handleEscapeKey(event) {
        if (event.key === 'Escape' && isSidecardOpen()) {
            event.preventDefault();
            closeSidecard();
        }
    }

    function isSidecardOpen() {
        return Boolean(sidecard && sidecard.classList.contains('entry-sidecard--open'));
    }

    function openSidecard(entry) {
        if (!sidecard || !noteForm || !noteField || !entryIdInput) {
            return;
        }

        currentEntry = entry;
        populateSidecard(entry);

        if (closeTimer) {
            clearTimeout(closeTimer);
            closeTimer = null;
        }

        sidecard.removeAttribute('hidden');
        sidecard.setAttribute('aria-hidden', 'false');
        document.body.classList.add('sidecard-open');
        window.requestAnimationFrame(() => {
            sidecard.classList.add('entry-sidecard--open');
            const closeButton = sidecard.querySelector('.entry-sidecard__close');
            (closeButton || noteField).focus();
        });
    }

    function populateSidecard(entry) {
        const data = entry.dataset;
        setText(fieldNodes.subject, data.entrySubject || '');
        setText(fieldNodes.date, data.entryDateLabel || '');
        setText(fieldNodes.teacher, data.entryTeacher || '');
        setText(fieldNodes.teacherInitial, getInitial(data.entryTeacher));
        applyTeacherRole(data.entryTeacherRole);
        setText(fieldNodes.time, data.entryTimeRange || '');
        setText(fieldNodes.badgeSubject, data.entrySubject || '');
        setText(fieldNodes.badgeClassroom, data.entryClassroom || '');
        setText(fieldNodes.badgeCourse, data.entryCourse || '');
        setText(fieldNodes.badgeGroup, data.entryGroup || '');
        setText(fieldNodes.series, data.entrySeries || '');

        toggleSection(sectionNodes.group, Boolean(data.entryGroup));
        toggleSection(sectionNodes.recurrence, Boolean(data.entrySeries));

        if (statusPill) {
            const code = data.entryStatusCode || 'upcoming';
            statusPill.className = `entry-status entry-status--${code}`;
        }

        setText(statusLabel, data.entryStatusLabel || '');

        const noteValue = data.entryNote || '';
        noteField.value = noteValue;
        entryIdInput.value = data.entryId || '';
        clearFeedback();
    }

    function setText(node, value) {
        if (node) {
            node.textContent = value;
        }
    }

    function getInitial(value) {
        if (!value) {
            return '';
        }
        return value.trim().charAt(0).toUpperCase();
    }

    function applyTeacherRole(role) {
        if (!fieldNodes.teacherInitial) {
            return;
        }
        fieldNodes.teacherInitial.classList.remove('member-card__avatar--admin', 'member-card__avatar--teacher');
        if (role === 'admin') {
            fieldNodes.teacherInitial.classList.add('member-card__avatar--admin');
        } else {
            fieldNodes.teacherInitial.classList.add('member-card__avatar--teacher');
        }
    }

    function toggleSection(node, shouldShow) {
        if (!node) {
            return;
        }

        if (shouldShow) {
            node.removeAttribute('hidden');
        } else {
            node.setAttribute('hidden', 'hidden');
        }
    }

    function closeSidecard() {
        if (!sidecard) {
            return;
        }

        sidecard.classList.remove('entry-sidecard--open');
        sidecard.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('sidecard-open');

        closeTimer = window.setTimeout(() => {
            sidecard.setAttribute('hidden', 'hidden');
            currentEntry = null;
        }, 220);
    }

    function clearFeedback() {
        if (feedbackNode) {
            feedbackNode.textContent = '';
            feedbackNode.classList.remove('entry-sidecard__feedback--success', 'entry-sidecard__feedback--error');
        }
    }

    function setFeedback(level, message) {
        if (!feedbackNode) {
            return;
        }

        feedbackNode.textContent = message || '';
        feedbackNode.classList.remove('entry-sidecard__feedback--success', 'entry-sidecard__feedback--error');

        if (level === 'success') {
            feedbackNode.classList.add('entry-sidecard__feedback--success');
        } else if (level === 'error') {
            feedbackNode.classList.add('entry-sidecard__feedback--error');
        }
    }

    async function handleNoteSubmit(event) {
        event.preventDefault();

        if (!currentEntry) {
            setFeedback('error', 'Select an entry first.');
            return;
        }

        clearFeedback();

        const formData = new FormData(noteForm);

        if (saveButton) {
            saveButton.disabled = true;
        }

        try {
            const response = await fetch(noteForm.action, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            });

            let payload = {};

            try {
                payload = await response.json();
            } catch (parseError) {
                payload = {};
            }

            if (response.ok && payload && payload.success) {
                const normalized = noteField.value.trim();
                currentEntry.dataset.entryNote = normalized;
                noteField.value = normalized;
                setFeedback('success', payload.message || 'Notes saved.');
            } else {
                setFeedback('error', (payload && payload.message) || 'Unable to save notes right now.');
            }
        } catch (networkError) {
            setFeedback('error', 'Unable to save notes right now.');
        } finally {
            if (saveButton) {
                saveButton.disabled = false;
            }
        }
    }

    function initSchedulerEnhancements() {
        if (hydrateSidecard()) {
            ensureBindings();
            bindNoteForm();
            bindSidecardDismiss();
        }
    }

    document.addEventListener('DOMContentLoaded', initSchedulerEnhancements);

    document.addEventListener('partial:updated', (event) => {
        if (!event.detail || !event.detail.container) {
            return;
        }

        if (event.detail.container.id === 'scheduler-content') {
            closeSidecard();
            initSchedulerEnhancements();
        }
    });
})();
