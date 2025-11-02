/** Provide shared AJAX utilities for partial updates and flash messages */
(function () {
    const REQUEST_HEADER = { 'X-Requested-With': 'XMLHttpRequest' };
    const FLASH_ICONS = {
        success: '<svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
        error: '<svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
        info: '<svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
        warning: '<svg class="icon" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M4.93 19h14.14a2 2 0 001.74-3l-7.07-12a2 2 0 00-3.42 0l-7.07 12a2 2 0 001.74 3z"></path></svg>'
    };

    const flashContainer = document.getElementById('flash-container');  // Where transient alerts render

    /** Build an icon element that matches the flash level */
    function createFlashIcon(level) {
        const template = document.createElement('template');
        template.innerHTML = (FLASH_ICONS[level] || FLASH_ICONS.info).trim();
        return template.content.firstChild;
    }

    /** Display a flash message element and schedule its removal */
    function showFlash(level, message) {
        if (!flashContainer || !message) {
            return;
        }

        const flash = document.createElement('div');
        flash.className = `flash ${level || 'info'}`;
        flash.appendChild(createFlashIcon(level));
        const span = document.createElement('span');
        span.textContent = message;
        flash.appendChild(span);
        flashContainer.appendChild(flash);

        setTimeout(() => {
            flash.classList.add('flash--fade');
            setTimeout(() => flash.remove(), 600);
        }, 6000);
    }

    /** Resolve a DOM container for partial updates */
    function resolveTarget(selector, fallbackElement) {
        if (selector) {
            return document.querySelector(selector);
        }
        if (fallbackElement) {
            const container = fallbackElement.closest('[data-partial-url]');
            if (container && container.id) {
                return container;
            }
        }
        return null;
    }

    /** Turn a raw URL or keyword into a partial-friendly URL */
    function buildPartialUrl(rawUrl, useLocationSearch = false) {
        const url = rawUrl instanceof URL
            ? new URL(rawUrl.href)
            : new URL(rawUrl, window.location.origin);

        if (useLocationSearch) {
            url.search = window.location.search;
        }

        if (!url.searchParams.has('partial')) {
            url.searchParams.set('partial', '1');
        }

        return url;
    }

    /** Fetch HTML content with the expected AJAX headers */
    async function fetchHtml(url) {
        const response = await fetch(url, {
            credentials: 'same-origin',
            headers: REQUEST_HEADER
        });

        if (!response.ok) {
            throw new Error('Request failed');
        }

        return response.text();
    }

    /** Update the scheduler export button so it mirrors the current filters */
    function updateSchedulerExport(scope) {
        const btn = scope.querySelector ? scope.querySelector('#export-csv-btn') : document.getElementById('export-csv-btn');
        if (!btn) {
            return;
        }

        if (!btn.dataset.baseHref) {
            btn.dataset.baseHref = btn.getAttribute('href');
        }

        const baseHref = btn.dataset.baseHref.split('?')[0];
        const search = window.location.search;
        btn.setAttribute('href', search ? `${baseHref}${search}` : baseHref);
    }

    /** Apply post-refresh behaviors after a partial update completes */
    function afterPartialUpdate(container) {
        if (!container) {
            return;
        }

        updateSchedulerExport(container);
        setupAutoRefresh(container);
    }

    /** Refresh a partial container with new markup retrieved over AJAX */
    async function refreshPartial(urlOrKeyword, targetSelector, options = {}) {
        const target = resolveTarget(targetSelector, options.sourceElement);
        if (!target) {
            return;
        }

        let url;
        let useLocationSearch = options.useLocationSearch ?? false;

        if (!urlOrKeyword || urlOrKeyword === 'current') {
            url = new URL(window.location.pathname + window.location.search, window.location.origin);  // Mirror current view
            useLocationSearch = true;
        } else {
            url = urlOrKeyword instanceof URL ? new URL(urlOrKeyword.href) : new URL(urlOrKeyword, window.location.origin);
        }

        const requestUrl = buildPartialUrl(url, useLocationSearch);

        try {
            const html = await fetchHtml(requestUrl);
            target.innerHTML = html;
            afterPartialUpdate(target);
        } catch (error) {
            showFlash('error', 'Failed to refresh content. Please try again.');
        }
    }

    /** Register periodic refresh behaviour for containers that opt in */
    function setupAutoRefresh(scope = document) {
        const containers = [];

        if (scope instanceof Element && scope.matches('[data-auto-refresh]')) {
            containers.push(scope);
        }

        if (scope.querySelectorAll) {
            scope.querySelectorAll('[data-auto-refresh]').forEach((el) => containers.push(el));
        }

        containers.forEach((container) => {
            if (!container.id || container.dataset.autoRefreshHandle) {
                return;
            }

            const interval = parseInt(container.dataset.autoRefresh, 10);
            if (!Number.isFinite(interval) || interval <= 0) {
                return;
            }

            const refreshUrl = container.dataset.partialUrl || container.dataset.autoRefreshUrl || window.location.pathname;
            const useLocationSearch = container.dataset.partialFollowsLocation === 'true';

            const tick = () => {
                refreshPartial(refreshUrl, `#${container.id}`, {
                    sourceElement: container,
                    useLocationSearch
                });
            };

            const handle = window.setInterval(tick, interval);
            container.dataset.autoRefreshHandle = String(handle);
        });
    }

    /** Submit a form as multipart/form-data over fetch and process the JSON reply */
    async function submitJsonForm(form, event) {
        if (form.dataset.ajaxPending === 'true') {
            return;
        }

        form.dataset.ajaxPending = 'true';  // Block duplicate submissions while pending

        const action = form.getAttribute('action') || window.location.href;
        const method = (form.getAttribute('method') || 'POST').toUpperCase();
        const formData = new FormData(form);

        if (event.submitter && event.submitter.name) {
            formData.append(event.submitter.name, event.submitter.value);
        }

        let response;
        try {
            response = await fetch(action, {
                method,
                body: formData,
                credentials: 'same-origin',
                headers: REQUEST_HEADER
            });
        } catch (networkError) {
            form.dataset.ajaxPending = 'false';
            showFlash('error', 'Network error. Please try again.');
            return;
        }

        let payload = {};
        const contentType = response.headers.get('content-type') || '';

        try {
            if (contentType.includes('application/json')) {
                payload = await response.json();
            } else {
                payload = { success: response.ok, message: await response.text() };
            }
        } catch (parseError) {
            payload = { success: response.ok, message: '' };
        }

        const success = Boolean(payload.success && response.ok);
        const level = payload.level || (success ? 'success' : 'error');

        if (payload.message) {
            showFlash(level, payload.message);
        }

        if (success) {
            if (form.dataset.ajaxReset === 'true') {
                form.reset();
                const pinnedOption = form.querySelector('#pinned-option');
                if (pinnedOption) {
                    pinnedOption.style.display = 'none';
                }
                const focusTarget = form.querySelector('textarea, input[type="text"], input[type="number"]');
                if (focusTarget) {
                    focusTarget.focus();
                }
            }

            const refreshUrl = form.dataset.ajaxRefresh;
            const targetSelector = form.dataset.ajaxTarget;
            await refreshPartial(refreshUrl, targetSelector, { sourceElement: form });
        }

        form.dataset.ajaxPending = 'false';
    }

    /** Submit a partial form and hydrate the target container with the response HTML */
    async function submitPartialForm(form, event) {
        const action = form.getAttribute('action') || window.location.pathname;
        const params = new URLSearchParams(new FormData(form));

        if (event.submitter && event.submitter.name) {
            params.append(event.submitter.name, event.submitter.value);
        }

        params.set('partial', '1');  // Ensure the server renders the partial view

        const url = new URL(action, window.location.origin);
        url.search = params.toString();

        const targetSelector = form.dataset.ajaxTarget;
        const target = resolveTarget(targetSelector, form);

        if (!target) {
            return;
        }

        try {
            const html = await fetchHtml(url);
            target.innerHTML = html;
            afterPartialUpdate(target);
        } catch (error) {
            showFlash('error', 'Unable to load data. Please try again.');
            return;
        }

        params.delete('partial');
        const historyUrl = new URL(action, window.location.origin);
        historyUrl.search = params.toString();
        window.history.pushState({}, '', historyUrl.pathname + historyUrl.search);
        updateSchedulerExport(document);
    }

    // Handle delegated submit events for AJAX-enabled forms
    document.addEventListener('submit', (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) {
            return;
        }

        const mode = form.dataset.ajax;
        if (!mode) {
            return;
        }

        event.preventDefault();

        if (mode === 'partial') {
            submitPartialForm(form, event);
        } else {
            submitJsonForm(form, event);
        }
    }, true);

    // Handle delegated clicks for links that request partial updates
    document.addEventListener('click', (event) => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
            return;
        }

        const link = event.target.closest('a[data-ajax-link]');
        if (!link) {
            return;
        }

        const targetSelector = link.dataset.ajaxTarget;
        const target = resolveTarget(targetSelector, link);

        if (!target) {
            return;
        }

        event.preventDefault();

        const rawUrl = new URL(link.href, window.location.origin);
        const requestUrl = buildPartialUrl(rawUrl, false);

        fetchHtml(requestUrl)
            .then((html) => {
                target.innerHTML = html;
                afterPartialUpdate(target);
                window.history.pushState({}, '', rawUrl.pathname + rawUrl.search);
            })
            .catch(() => {
                showFlash('error', 'Unable to load content. Please try again.');
            });
    });

    // Re-fetch partials when the user navigates via the browser history
    window.addEventListener('popstate', () => {
        document.querySelectorAll('[data-partial-url]').forEach((container) => {
            const sourceUrl = container.dataset.partialUrl || 'current';
            const followsLocation = container.dataset.partialFollowsLocation === 'true';
            const refreshUrl = followsLocation ? window.location.href : sourceUrl;

            refreshPartial(refreshUrl, `#${container.id}`, {
                sourceElement: container,
                useLocationSearch: followsLocation
            });
        });

        updateSchedulerExport(document);
    });

    // Apply initial enhancements once the DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        updateSchedulerExport(document);
        setupAutoRefresh();
    });
})();
