/* Copyright © William Alexakis. All Rights Reserved. Use governed by LICENSE file. */

/** Toggle between light and dark modes while persisting the preference */
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');  // Read current theme flag
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';

    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);  // Persist choice for the next visit
}

/** Restore the previously chosen theme when the page loads */
(function () {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
})();
