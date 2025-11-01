/** Bootstraps the client-side code editor backed by Monaco and Pyodide */
(function () {
    const initialCodeElement = document.getElementById("initial-code-data");
    let initialCode = "";

    if (initialCodeElement) {
        try {
            initialCode = JSON.parse(initialCodeElement.textContent);
        } catch (error) {
            initialCode = initialCodeElement.textContent || "";
        }

        if (typeof initialCodeElement.remove === "function") {
            initialCodeElement.remove();  // Remove embedded data element once consumed
        }
    }

    const PYODIDE_BASE_URL = "https://cdn.jsdelivr.net/pyodide/v0.24.1/full/";

    const runButton = document.getElementById("run-button");
    const stopButton = document.getElementById("stop-button");
    const importButton = document.getElementById("import-button");
    const exportButton = document.getElementById("export-button");
    const fileInput = document.getElementById("file-input");
    const statusBadge = document.getElementById("status-badge");
    const outputArea = document.getElementById("output-area");

    let editorInstance = null;
    let worker = null;
    let workerReady = false;
    let isRunning = false;
    let currentFilename = "code.py";
    let queuedCode = null;

    /** Update the status badge to reflect the current editor state */
    function updateStatus(state, label) {
        const validStates = ["idle", "loading", "running", "success", "error", "stopped"];
        const safeState = validStates.includes(state) ? state : "idle";

        statusBadge.className = "status-badge status-" + safeState;
        statusBadge.innerHTML = '<span class="status-dot"></span>' + label;
    }

    /** Remove all previous output lines from the console area */
    function clearOutput() {
        outputArea.innerHTML = "";
    }

    /** Append a formatted output line to the console area */
    function appendOutput(text, type) {
        const line = document.createElement("div");
        line.className = "output-line output-" + (type || "stdout");
        line.textContent = text;
        outputArea.appendChild(line);
        outputArea.scrollTop = outputArea.scrollHeight;
    }

    /** Run the queued code inside the Pyodide worker */
    function executeCode(code) {
        queuedCode = null;
        clearOutput();
        setRunningState(true);
        updateStatus("running", "Running...");
        worker.postMessage({ type: "run", code });
    }

    /** Toggle button states and internal flags while the worker executes code */
    function setRunningState(running) {
        isRunning = running;
        runButton.disabled = running || !workerReady;
        stopButton.disabled = !running;
    }

    /** Rebuild the Pyodide web worker and warm it up for execution */
    function rebuildWorker() {
        if (worker) {
            worker.terminate();  // Tear down old worker to avoid lingering state
        }

        const workerSource = `
            let pyodideInstance;

            async function ensurePyodide() {
                if (!pyodideInstance) {
                    self.postMessage({ type: "status", payload: "loading" });
                    importScripts("${PYODIDE_BASE_URL}pyodide.js");
                    pyodideInstance = await loadPyodide({ indexURL: "${PYODIDE_BASE_URL}" });

                    pyodideInstance.setStdout({
                        batched(text) {
                            if (text) {
                                self.postMessage({ type: "stdout", payload: text });
                            }
                        }
                    });

                    pyodideInstance.setStderr({
                        batched(text) {
                            if (text) {
                                self.postMessage({ type: "stderr", payload: text });
                            }
                        }
                    });

                    pyodideInstance.runPython(\`
import builtins
_blocked_modules = {"pyodide", "pyodide_js", "js", "micropip"}
_original_import = builtins.__import__
def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".", 1)[0]
    if root in _blocked_modules:
        raise ImportError(f"Importing {root!r} is disabled in this editor.")
    return _original_import(name, globals, locals, fromlist, level)
builtins.__import__ = _safe_import
\`);

                    self.fetch = async () => {
                        throw new Error("Network access is disabled in this environment.");
                    };

                    self.postMessage({ type: "ready" });
                }

                return pyodideInstance;
            }

            self.onmessage = async (event) => {
                const { type, code } = event.data;

                if (type === "warmup") {
                    try {
                        await ensurePyodide();
                    } catch (error) {
                        const message = error && error.message ? error.message : String(error);
                        self.postMessage({ type: "python-error", payload: message });
                        self.postMessage({ type: "status", payload: "error" });
                    }
                    return;
                }

                if (type === "run") {
                    const runtime = await ensurePyodide();
                    self.postMessage({ type: "status", payload: "running" });

                    let namespace;

                    try {
                        namespace = runtime.globals.get("dict")();
                        namespace.set("__builtins__", runtime.globals.get("__builtins__"));
                        await runtime.runPythonAsync(code, { globals: namespace });
                        self.postMessage({ type: "status", payload: "success" });
                    } catch (error) {
                        const message = error && error.message ? error.message : String(error);
                        self.postMessage({ type: "python-error", payload: message });
                        self.postMessage({ type: "status", payload: "error" });
                    } finally {
                        if (namespace) {
                            try {
                                namespace.destroy();
                            } catch (cleanupError) {
                                // ignore
                            }
                        }

                        self.postMessage({ type: "done" });
                    }
                }
            };
        `;

        const blob = new Blob([workerSource], { type: "application/javascript" });
        const workerUrl = URL.createObjectURL(blob);
        worker = new Worker(workerUrl);
        URL.revokeObjectURL(workerUrl);

        worker.onmessage = (event) => {
            const { type, payload } = event.data;

            switch (type) {
                case "ready":
                    workerReady = true;
                    if (!isRunning && !queuedCode) {
                        updateStatus("idle", "Ready");
                    }
                    runButton.disabled = false;
                    if (queuedCode) {
                        const codeToRun = queuedCode;
                        queuedCode = null;
                        executeCode(codeToRun);
                    }
                    break;

                case "status":
                    if (payload === "loading") {
                        updateStatus("loading", "Preparing runtime...");
                    } else if (payload === "running") {
                        updateStatus("running", "Running...");
                    } else if (payload === "success") {
                        updateStatus("success", "Completed");
                    } else if (payload === "error") {
                        updateStatus("error", "Error");
                    }
                    break;

                case "stdout":
                    appendOutput(payload, "stdout");
                    break;

                case "stderr":
                    appendOutput(payload, "stderr");
                    break;

                case "python-error":
                    appendOutput(payload, "error");
                    break;

                case "done":
                    setRunningState(false);
                    break;

                default:
                    break;
            }
        };

        worker.onerror = (error) => {
            appendOutput("Worker error: " + error.message, "error");
            updateStatus("error", "Worker error");
            setRunningState(false);
            workerReady = false;
        };

        queuedCode = null;
        workerReady = false;
        runButton.disabled = true;
        stopButton.disabled = true;

        try {
            worker.postMessage({ type: "warmup" });  // Preload runtime to reduce first-run delay
        } catch (error) {
            appendOutput("Failed to initialize Python runtime.", "error");
        }
    }

    /** Lazily ensure a worker exists before attempting to send jobs */
    function ensureWorker() {
        if (!worker) {
            rebuildWorker();
        }
    }

    /** Load the Monaco editor assets and instantiate the editor instance */
    function initMonaco() {
        const loaderUrl = "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs";

        require.config({ paths: { vs: loaderUrl } });

        window.MonacoEnvironment = {
            getWorkerUrl: function () {
                const proxy = `
                    self.MonacoEnvironment = { baseUrl: "${loaderUrl}/" };
                    importScripts("${loaderUrl}/base/worker/workerMain.js");
                `;
                return URL.createObjectURL(new Blob([proxy], { type: "text/javascript" }));
            }
        };

        require(["vs/editor/editor.main"], function () {
            editorInstance = monaco.editor.create(document.getElementById("code-editor"), {
                value: initialCode,
                language: "python",
                automaticLayout: true,
                fontSize: 14,
                theme: document.documentElement.getAttribute("data-theme") === "dark" ? "vs-dark" : "vs",
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                tabSize: 4,
                wordWrap: "on"
            });

            syncEditorTheme();
        });
    }

    /** Synchronize the Monaco theme with the surrounding site theme */
    function syncEditorTheme() {
        if (!window.monaco || !editorInstance) {
            return;
        }

        const isDark = document.documentElement.getAttribute("data-theme") === "dark";
        monaco.editor.setTheme(isDark ? "vs-dark" : "vs");
    }

    /** Observe theme attribute changes and update Monaco in response */
    const themeObserver = new MutationObserver(function (mutations) {
        for (const mutation of mutations) {
            if (mutation.type === "attributes" && mutation.attributeName === "data-theme") {
                syncEditorTheme();
            }
        }
    });

    themeObserver.observe(document.documentElement, { attributes: true });

    runButton.addEventListener("click", function () {
        ensureWorker();

        if (!editorInstance) {
            appendOutput("Editor is still loading. Please wait.", "info");  // Guard against early clicks
            return;
        }

        const code = editorInstance.getValue();

        if (!code.trim()) {
            appendOutput("Nothing to run. Add some Python code first.", "info");
            return;
        }

        if (!workerReady) {
            queuedCode = code;
            runButton.disabled = true;
            stopButton.disabled = true;
            clearOutput();
            appendOutput("Preparing Python runtime. Your code will run automatically once ready.", "info");
            updateStatus("loading", "Preparing runtime...");
            return;
        }

        executeCode(code);
    });

        stopButton.addEventListener("click", function () {
            if (!isRunning) {
                return;
            }

            appendOutput("Execution stopped by user.", "info");
            updateStatus("stopped", "Stopped");
            setRunningState(false);
            queuedCode = null;
            rebuildWorker();  // Rebuild to guarantee a clean interpreter
        });

        importButton.addEventListener("click", function () {
            fileInput.click();  // Trigger hidden file picker for uploads
        });

        exportButton.addEventListener("click", function () {
            if (!editorInstance) {
                appendOutput("Editor is still loading. Please wait.", "info");
            return;
        }

        const code = editorInstance.getValue();
        const blob = new Blob([code], { type: "text/x-python" });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = currentFilename || "code.py";
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(url);
    });

    fileInput.addEventListener("change", function (event) {
        const file = event.target.files[0];

        if (!file) {
            return;
        }

        if (!/\.(py|txt)$/i.test(file.name)) {
            appendOutput("Only .py or .txt files are allowed.", "error");
            fileInput.value = "";
            return;
        }

        if (file.size > 200 * 1024) {
            appendOutput("File is too large. Maximum supported size is 200 KB.", "error");
            fileInput.value = "";
            return;
        }

        const reader = new FileReader();

        reader.onload = function (e) {
            if (editorInstance) {
                editorInstance.setValue(e.target.result);
                appendOutput("Loaded file: " + file.name, "info");
                currentFilename = file.name;  // Track name for export default
            } else {
                appendOutput("Editor is still loading. Please wait.", "info");
            }
        };

        reader.onerror = function () {
            appendOutput("Failed to read the selected file.", "error");
        };

        reader.readAsText(file, "utf-8");
        fileInput.value = "";
    });

    ensureWorker();
    initMonaco();
})();
