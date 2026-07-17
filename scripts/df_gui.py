"""
modules/df/scripts/df_gui.py

Developer operations GUI for `df` - a pure launcher over commands that
already exist (build.bat, carla_bridge.py, df_dll_sim_mcap.py). Every button
shells out; nothing here reimplements build/CARLA/replay logic or edits a
YAML value - dropdowns are populated by reading conf/build.yml, CMakePresets,
and scanning the filesystem, never hardcoded. Subprocess output is NOT
captured into the GUI - it's left to inherit this app's own console (the cmd
window gui.bat opened), so there's no in-app log panel to keep in sync;
buttons just show run/done state. CARLA/Foxglove exe paths are persisted as
real user-scope Windows env vars (CARLA_ROOT/FOXGLOVE_EXE via setx), not a
repo-local file - they're machine facts, not per-clone ones.
See docs/df_dev_gui_plan.md (superproject root) for the full design.

Workflow, top to bottom:
  1. BUILD & TEST           - build.bat <project> <target> <platform>
  2. CARLA                  - launch the server, run the live bridge
  3. REPLAY & FOXGLOVE VIZ  - replay a recorded .mcap, no CARLA needed
  4. PUBLISH                - conan create + upload to the adas-local remote

Run:
    gui.bat
    (or: py df_gui.py, from this folder)
"""

import json
import os
import socket
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, ttk

import yaml

# ── paths ─────────────────────────────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))          # modules/df/scripts
DF_ROOT = os.path.dirname(_THIS_DIR)                              # modules/df
SUPERPROJECT_ROOT = os.path.dirname(os.path.dirname(DF_ROOT))     # up: modules -> root

sys.path.insert(0, os.path.join(SUPERPROJECT_ROOT, "scripts"))
import conan_publish  # noqa: E402 - path must be set up first

PACKAGE_NAME = "adas-df"

CONF_DIR = os.path.join(SUPERPROJECT_ROOT, "conf")
DF_BUILD_YML = os.path.join(DF_ROOT, "conf", "build.yml")
DF_CMAKE_PRESETS = os.path.join(DF_ROOT, "CMakePresets.json")
DF_CMAKELISTS = os.path.join(DF_ROOT, "CMakeLists.txt")
CARLA_DIR = os.path.join(DF_ROOT, "tools", "carla")
REPLAY_DIR = os.path.join(CARLA_DIR, "replay")
SCENARIOS_DIR = os.path.join(DF_ROOT, "tests", "carla_scenarios")
TESTRUNS_DIR = os.path.join(DF_ROOT, "tests", "carla_testruns")
EXPORTS_DIR = os.path.join(TESTRUNS_DIR, "exports")
GUI_CFG_PATH = os.path.join(_THIS_DIR, "df_gui_config.json")

# -vulkan avoids the D3D device-lost crash under HAGS (see tools/carla/README.md
# "Known issues"); -windowed + explicit resolution is confirmed necessary
# alongside it on this machine, not just a preference.
CARLA_LAUNCH_FLAGS = ["-vulkan", "-windowed", "-ResX=800", "-ResY=600"]

# matches foxglove_stream.py's DEFAULT_PORT - --viz has no flag to change it,
# so a leftover process from a previous --viz run (e.g. the BEV window closed
# via its own X button instead of a keypress) leaves this bound and the next
# run fails deep inside foxglove.start_server() with a raw traceback.
FOXGLOVE_PORT = 8765

# Machine-level facts (where CARLA/Foxglove are installed) don't belong in a
# gitignored file inside a repo clone - a fresh clone would lose them, and
# they're the same regardless of which clone/project you're using. Persisted
# as real Windows user-scope env vars instead (setx, no admin needed), same
# CARLA_ROOT convention bumpEstimate's own launcher.py already uses.
CARLA_ROOT_ENV = "CARLA_ROOT"
FOXGLOVE_EXE_ENV = "FOXGLOVE_EXE"


def _port_in_use(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def _set_persistent_env(name, value):
    """Updates os.environ so this already-running process sees it
    immediately, and persists via setx (HKCU\\Environment, user-scope, no
    admin) so future terminals/processes - including a completely different
    repo clone - see it too, without asking the user again."""
    os.environ[name] = value
    try:
        subprocess.run(["setx", name, value], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        pass


# ── config persistence ────────────────────────────────────────────────────────

def _load_cfg():
    try:
        with open(GUI_CFG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cfg(**updates):
    cfg = _load_cfg()
    cfg.update(updates)
    try:
        with open(GUI_CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError:
        pass


# ── data helpers (dropdowns - read-only, never edit these files, never
#    hardcoded lists) ─────────────────────────────────────────────────────────

def _list_projects():
    if not os.path.isdir(CONF_DIR):
        return ["base"]
    names = sorted(
        os.path.splitext(f)[0] for f in os.listdir(CONF_DIR) if f.endswith(".yaml")
    )
    return names or ["base"]


def _list_platforms(project):
    try:
        with open(DF_BUILD_YML, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        platforms = data["variants"][project]["sil"]["platforms"]
        return [p["build"] for p in platforms] or ["vs2026"]
    except (OSError, KeyError, IndexError, TypeError, yaml.YAMLError):
        return ["vs2026"]


def _list_targets():
    """build.bat's valid <target> values aren't listed in any YAML (gtest
    isn't a project-scoped 'part') - the actual source of truth is which
    configurePresets exist in CMakePresets.json, each named <target>-<platform>."""
    try:
        with open(DF_CMAKE_PRESETS, encoding="utf-8") as f:
            data = json.load(f)
        names = set()
        for preset in data.get("configurePresets", []):
            if preset.get("hidden"):
                continue
            name = preset.get("name", "")
            if "-" in name:
                names.add(name.split("-", 1)[0])
        return sorted(names) or ["sil", "gtest"]
    except (OSError, json.JSONDecodeError, KeyError):
        return ["sil", "gtest"]


def _list_scenarios():
    if not os.path.isdir(SCENARIOS_DIR):
        return []
    return sorted(f for f in os.listdir(SCENARIOS_DIR) if f.endswith(".yaml"))


def _list_recordings():
    if not os.path.isdir(TESTRUNS_DIR):
        return []
    return sorted(f for f in os.listdir(TESTRUNS_DIR) if f.endswith(".mcap"))


def _current_version():
    """Reads the VERSION currently declared in CMakeLists.txt - the same
    line conanfile.py's set_version() reads, and what `conan create` would
    publish right now if you didn't bump it first."""
    try:
        import re
        with open(DF_CMAKELISTS, encoding="utf-8") as f:
            content = f.read()
        match = re.search(
            r"project\(\s*" + re.escape(PACKAGE_NAME) + r"\s+VERSION\s+([0-9]+\.[0-9]+\.[0-9]+)",
            content, re.IGNORECASE,
        )
        return match.group(1) if match else "?"
    except OSError:
        return "?"


# ── hover tooltips (Tkinter has no built-in widget for this) ──────────────────

class _Tooltip:
    """Small hover tooltip - binds <Enter>/<Leave> on a widget to show/hide a
    borderless Toplevel with a text label near the cursor."""

    def __init__(self, widget, text):
        self._widget = widget
        self._text = text
        self._tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None):
        if self._tip is not None:
            return
        x = self._widget.winfo_rootx() + 10
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self._tip, text=self._text, justify="left", wraplength=340,
                 background="#ffffe0", relief="solid", borderwidth=1,
                 font=("Segoe UI", 8)).pack(ipadx=4, ipady=2)

    def _hide(self, _event=None):
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


# ── subprocess runner ─────────────────────────────────────────────────────────

class _ProcessRunner:
    """Runs one or more commands in sequence on a background thread so the UI
    stays responsive. Output is NOT captured - each command inherits this
    app's own console, same window the user launched gui.bat from. Stops the
    sequence early if a command fails or stop() is called.

    Bug #18: if `cmds` is the editable-aware publish sequence ([editable
    remove, create, upload, editable add]) and stop() lands after the
    `editable remove` has completed but before the final `editable add`
    runs, the package's editable registration would otherwise be left
    removed with no restore - silently breaking the user's own local dev
    loop. _run() detects exactly that condition and runs the restore
    command itself before reporting done; on_done then receives a second
    `editable_restored` arg (True/False) only when this happened, so
    existing single-arg on_done callbacks (build/CARLA/replay, none of
    which run an editable-aware sequence) are unaffected."""

    def __init__(self, cmds, cwd, on_done=None):
        self._cmds = cmds if isinstance(cmds[0], list) else [cmds]
        self._cwd = cwd
        self._on_done = on_done
        self._proc = None
        self._stopped = False
        self._completed = 0

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stopped = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def _needs_editable_restore(self):
        cmds = self._cmds
        return (
            len(cmds) > 1
            and cmds[0][:3] == ["conan", "editable", "remove"]
            and cmds[-1][:3] == ["conan", "editable", "add"]
            and 0 < self._completed < len(cmds) - 1
        )

    def _run(self):
        rc = 0
        for cmd in self._cmds:
            if self._stopped:
                break
            try:
                self._proc = subprocess.Popen(cmd, cwd=self._cwd)
                rc = self._proc.wait()
            except OSError:
                rc = -1
            if rc != 0:
                break
            self._completed += 1

        restored = None
        if self._stopped and self._needs_editable_restore():
            try:
                restored = subprocess.run(self._cmds[-1], cwd=self._cwd).returncode == 0
            except OSError:
                restored = False

        if self._on_done:
            if restored is not None:
                self._on_done(rc, restored)
            else:
                self._on_done(rc)


# ── main app ──────────────────────────────────────────────────────────────────

class DfGuiApp:

    def __init__(self, root):
        self.root = root
        root.title("df - Developer Operations")
        root.minsize(680, 480)

        self._cfg = _load_cfg()

        self._build_runner = None
        self._carla_runner = None
        self._replay_runner = None
        self._carla_proc = None  # CarlaUE4.exe handle - separate from the bridge runner

        self._build_buildtest_section()
        self._build_carla_section()
        self._build_replay_section()
        self._build_publish_section()

    # ── BUILD & TEST ──────────────────────────────────────────────────────────

    def _build_buildtest_section(self):
        frame = ttk.LabelFrame(self.root, text="BUILD & TEST", padding=8)
        frame.pack(fill="x", padx=10, pady=(10, 4))

        row1 = ttk.Frame(frame)
        row1.pack(fill="x")
        ttk.Label(row1, text="Project:").pack(side="left")
        self._project = tk.StringVar(value=self._cfg.get("project", "base"))
        project_cb = ttk.Combobox(row1, textvariable=self._project, values=_list_projects(),
                                   state="readonly", width=14)
        project_cb.pack(side="left", padx=(4, 12))
        project_cb.bind("<<ComboboxSelected>>", self._on_project_changed)

        ttk.Label(row1, text="Target:").pack(side="left")
        self._target = tk.StringVar(value=self._cfg.get("target", "sil"))
        target_cb = ttk.Combobox(row1, textvariable=self._target, values=_list_targets(),
                                  state="readonly", width=10)
        target_cb.pack(side="left", padx=(4, 0))

        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=(4, 0))
        ttk.Label(row2, text="Platform:").pack(side="left")
        self._platform = tk.StringVar(value=self._cfg.get("platform", "vs2026"))
        self._platform_cb = ttk.Combobox(row2, textvariable=self._platform,
                                          values=_list_platforms(self._project.get()),
                                          state="readonly", width=14)
        self._platform_cb.pack(side="left", padx=(4, 12))

        self._clean = tk.BooleanVar(value=False)
        clean_cb = ttk.Checkbutton(row2, text="clean", variable=self._clean)
        clean_cb.pack(side="left", padx=(0, 12))
        _Tooltip(clean_cb, "Deletes the existing build-<target>-<platform>\n"
                            "folder first, forcing a full rebuild instead of\n"
                            "an incremental one.")

        self._build_run_btn = ttk.Button(row2, text="▶ Build", command=self._run_build)
        self._build_run_btn.pack(side="left")
        self._build_stop_btn = ttk.Button(row2, text="■ Stop", command=self._stop_build,
                                           state="disabled")
        self._build_stop_btn.pack(side="left", padx=4)

        self._build_cmd_label = ttk.Label(frame, text="", foreground="#555",
                                           font=("Consolas", 8))
        self._build_cmd_label.pack(anchor="w", pady=(6, 0))
        self._build_status = ttk.Label(frame, text="idle", foreground="gray")
        self._build_status.pack(anchor="w")

    def _on_project_changed(self, _=None):
        self._platform_cb.config(values=_list_platforms(self._project.get()))
        _save_cfg(project=self._project.get())

    def _run_build(self):
        project, target, platform = self._project.get(), self._target.get(), self._platform.get()
        _save_cfg(project=project, target=target, platform=platform)
        cmd = ["cmd.exe", "/c", "build.bat", project, target, platform] + (
            ["clean"] if self._clean.get() else [])
        self._build_run_btn.config(state="disabled")
        self._build_stop_btn.config(state="normal")
        self._build_cmd_label.config(text="$ " + " ".join(cmd) + f"   (cwd: {DF_ROOT})")
        self._build_status.config(text="running...", foreground="darkorange")
        self._build_runner = _ProcessRunner(cmd, DF_ROOT, on_done=self._on_build_done)
        self._build_runner.start()

    def _stop_build(self):
        if self._build_runner:
            self._build_runner.stop()

    def _on_build_done(self, rc):
        self.root.after(0, self._build_done_ui, rc)

    def _build_done_ui(self, rc):
        self._build_run_btn.config(state="normal")
        self._build_stop_btn.config(state="disabled")
        ok = rc == 0
        self._build_status.config(text=f"done (rc={rc})" if ok else f"exited rc={rc}",
                                   foreground="#2a9d2a" if ok else "#c0392b")

    # ── CARLA ─────────────────────────────────────────────────────────────────

    def _build_carla_section(self):
        frame = ttk.LabelFrame(self.root, text="CARLA", padding=8)
        frame.pack(fill="x", padx=10, pady=4)

        row1 = ttk.Frame(frame)
        row1.pack(fill="x")
        ttk.Label(row1, text="CARLA exe:").pack(side="left")
        carla_root = os.environ.get(CARLA_ROOT_ENV, "")
        default_carla_exe = os.path.join(carla_root, "CarlaUE4.exe") if carla_root else ""
        self._carla_exe = tk.StringVar(value=default_carla_exe)
        carla_exe_entry = ttk.Entry(row1, textvariable=self._carla_exe, width=40)
        carla_exe_entry.pack(side="left", padx=4)
        _Tooltip(carla_exe_entry,
                  "Persisted as the CARLA_ROOT environment variable (setx,\n"
                  "user-scope) once set via Browse or a successful launch -\n"
                  "set once, every repo clone and future session picks it up\n"
                  "automatically, no re-browsing needed.")
        ttk.Button(row1, text="Browse", command=self._browse_carla_exe).pack(side="left")
        self._carla_launch_btn = ttk.Button(row1, text="Launch CARLA Server",
                                             command=self._launch_carla)
        self._carla_launch_btn.pack(side="left", padx=(8, 0))
        _Tooltip(self._carla_launch_btn,
                  "Starts CarlaUE4.exe with -vulkan -windowed -ResX=800\n"
                  "-ResY=600. -vulkan avoids a known D3D crash; must be run\n"
                  "as Administrator on this machine. Takes ~30s to load -\n"
                  "wait for it before running the bridge below.")
        self._carla_status = ttk.Label(row1, text="not started", foreground="gray", width=16)
        self._carla_status.pack(side="left", padx=6)

        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Label(row2, text="Scenario:").pack(side="left")
        self._scenario = tk.StringVar(value=self._cfg.get("scenario", ""))
        scenarios = _list_scenarios()
        self._scenario_cb = ttk.Combobox(row2, textvariable=self._scenario, values=scenarios,
                                          state="readonly", width=30)
        self._scenario_cb.pack(side="left", padx=4)
        if scenarios and self._scenario.get() not in scenarios:
            self._scenario_cb.current(0)
        self._carla_record = tk.BooleanVar(value=False)
        record_cb = ttk.Checkbutton(row2, text="--record", variable=self._carla_record)
        record_cb.pack(side="left", padx=8)
        _Tooltip(record_cb,
                  "Also writes this run's exact inputs plus a chase-view\n"
                  "video to tests/carla_testruns/<scenario>.mcap, so it can\n"
                  "be replayed below without a CARLA server later.")
        self._carla_run_btn = ttk.Button(row2, text="▶ Run Bridge",
                                          command=self._run_carla_bridge)
        self._carla_run_btn.pack(side="left", padx=4)
        self._carla_stop_btn = ttk.Button(row2, text="■ Stop", command=self._stop_carla_bridge,
                                           state="disabled")
        self._carla_stop_btn.pack(side="left")

        self._carla_cmd_label = ttk.Label(frame, text="", foreground="#555",
                                           font=("Consolas", 8))
        self._carla_cmd_label.pack(anchor="w", pady=(6, 0))
        self._carla_run_status = ttk.Label(frame, text="idle", foreground="gray")
        self._carla_run_status.pack(anchor="w")

    def _browse_carla_exe(self):
        path = filedialog.askopenfilename(
            title="Select CarlaUE4.exe", filetypes=[("Executable", "*.exe"), ("All files", "*.*")])
        if path:
            self._carla_exe.set(path)
            _set_persistent_env(CARLA_ROOT_ENV, os.path.dirname(path))

    def _launch_carla(self):
        exe = self._carla_exe.get().strip()
        if not exe or not os.path.isfile(exe):
            self._carla_status.config(text="exe not found", foreground="#c0392b")
            return
        if self._carla_proc and self._carla_proc.poll() is None:
            self._carla_status.config(text="already running", foreground="#2a9d2a")
            return
        _set_persistent_env(CARLA_ROOT_ENV, os.path.dirname(exe))
        try:
            self._carla_proc = subprocess.Popen([exe] + CARLA_LAUNCH_FLAGS,
                                                 cwd=os.path.dirname(exe))
            self._carla_status.config(text="starting... ~30s", foreground="darkorange")
            self._carla_launch_btn.config(state="disabled")
            self.root.after(500, self._poll_carla_server)
        except OSError as exc:
            self._carla_status.config(text=f"error: {exc}", foreground="#c0392b")

    def _poll_carla_server(self):
        if self._carla_proc is None:
            return
        rc = self._carla_proc.poll()
        if rc is not None:
            self._carla_status.config(text=f"exited rc={rc}", foreground="#c0392b")
            self._carla_launch_btn.config(state="normal")
        else:
            self._carla_status.config(text="running", foreground="#2a9d2a")
            self._carla_launch_btn.config(state="normal")

    def _run_carla_bridge(self):
        scenario = self._scenario.get().strip()
        if not scenario:
            self._carla_run_status.config(text="[error] No scenario selected.", foreground="#c0392b")
            return
        _save_cfg(scenario=scenario)
        cmd = ["py", "-3.12", "carla_bridge.py", scenario]
        if self._carla_record.get():
            cmd.append("--record")
        self._carla_run_btn.config(state="disabled")
        self._carla_stop_btn.config(state="normal")
        self._carla_cmd_label.config(text="$ " + " ".join(cmd) + f"   (cwd: {CARLA_DIR})")
        self._carla_run_status.config(text="running...", foreground="darkorange")
        self._carla_runner = _ProcessRunner(cmd, CARLA_DIR, on_done=self._on_carla_done)
        self._carla_runner.start()

    def _stop_carla_bridge(self):
        if self._carla_runner:
            self._carla_runner.stop()

    def _on_carla_done(self, rc):
        self.root.after(0, self._carla_done_ui, rc)

    def _carla_done_ui(self, rc):
        self._carla_run_btn.config(state="normal")
        self._carla_stop_btn.config(state="disabled")
        ok = rc == 0
        self._carla_run_status.config(text=f"done (rc={rc})" if ok else f"exited rc={rc}",
                                       foreground="#2a9d2a" if ok else "#c0392b")

    # ── REPLAY & FOXGLOVE VIZ ────────────────────────────────────────────────

    def _build_replay_section(self):
        frame = ttk.LabelFrame(self.root, text="REPLAY & FOXGLOVE VIZ", padding=8)
        frame.pack(fill="x", padx=10, pady=(4, 10))

        row0 = ttk.Frame(frame)
        row0.pack(fill="x", pady=(0, 4))
        ttk.Label(row0, text="Foxglove exe:").pack(side="left")
        self._foxglove_exe = tk.StringVar(value=os.environ.get(FOXGLOVE_EXE_ENV, ""))
        foxglove_exe_entry = ttk.Entry(row0, textvariable=self._foxglove_exe, width=40)
        foxglove_exe_entry.pack(side="left", padx=4)
        _Tooltip(foxglove_exe_entry,
                  "Persisted as the FOXGLOVE_EXE environment variable (setx,\n"
                  "user-scope) once set via Browse - set once, every repo\n"
                  "clone and future session picks it up automatically.\n"
                  "Left blank, \"Open Foxglove Studio\" below falls back to\n"
                  "opening studio.foxglove.dev in your browser instead.")
        ttk.Button(row0, text="Browse", command=self._browse_foxglove_exe).pack(side="left")

        row1 = ttk.Frame(frame)
        row1.pack(fill="x")
        ttk.Label(row1, text="Recording:").pack(side="left")
        self._recording = tk.StringVar(value=self._cfg.get("recording", ""))
        recordings = _list_recordings()
        self._recording_cb = ttk.Combobox(row1, textvariable=self._recording, values=recordings,
                                           state="readonly", width=30)
        self._recording_cb.pack(side="left", padx=4)
        if recordings and self._recording.get() not in recordings:
            self._recording_cb.current(0)
        ttk.Button(row1, text="↻", width=3, command=self._refresh_recordings).pack(
            side="left", padx=4)

        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=(4, 0))
        self._replay_viz = tk.BooleanVar(value=False)
        self._replay_step = tk.BooleanVar(value=False)
        self._replay_nowait = tk.BooleanVar(value=False)
        viz_cb = ttk.Checkbutton(row2, text="--viz", variable=self._replay_viz)
        viz_cb.pack(side="left")
        _Tooltip(viz_cb,
                  "Opens a live 2D bird's-eye-view window (object boxes,\n"
                  "ego at the bottom, critical object turns amber/red on\n"
                  "pre-warning) AND starts a Foxglove server at\n"
                  "ws://localhost:8765. Off = console print only, no windows\n"
                  "either way - the console line keeps printing regardless.\n"
                  "\n"
                  "Foxglove Studio itself doesn't remember panels across a\n"
                  "fresh connection - every time you (re)connect, add an\n"
                  "Image panel on topic carla/chase_camera and a Plot or\n"
                  "Raw Messages panel on topic df/aeb_outputs to see them\n"
                  "again (or save a Layout in Foxglove once so it's there\n"
                  "next time you load that layout).")
        step_cb = ttk.Checkbutton(row2, text="--step", variable=self._replay_step)
        step_cb.pack(side="left", padx=8)
        _Tooltip(step_cb,
                  "Advance one simulation cycle at a time (press a key/Enter\n"
                  "to go to the next one) instead of real-time playback -\n"
                  "for inspecting one confusing decision cycle by cycle.")
        nowait_cb = ttk.Checkbutton(row2, text="--no-wait", variable=self._replay_nowait)
        nowait_cb.pack(side="left")
        _Tooltip(nowait_cb,
                  "Only matters together with --viz: skips waiting for a\n"
                  "Foxglove Studio connection before starting, and skips\n"
                  "holding the BEV window open at the end. Without --viz\n"
                  "there's nothing to wait for, so this does nothing on its own.")
        self._replay_run_btn = ttk.Button(row2, text="▶ Run Replay", command=self._run_replay)
        self._replay_run_btn.pack(side="left", padx=8)
        self._replay_stop_btn = ttk.Button(row2, text="■ Stop", command=self._stop_replay,
                                            state="disabled")
        self._replay_stop_btn.pack(side="left")
        foxglove_btn = ttk.Button(row2, text="Open Foxglove Studio", command=self._open_foxglove)
        foxglove_btn.pack(side="left", padx=8)
        _Tooltip(foxglove_btn,
                  "Launches the Foxglove exe above if set, else opens\n"
                  "studio.foxglove.dev in your browser. Either way, once open:\n"
                  "connect to ws://localhost:8765, then add an Image panel\n"
                  "on carla/chase_camera and a Plot/Raw Messages panel on\n"
                  "df/aeb_outputs - a fresh connection starts with no panels,\n"
                  "Foxglove doesn't remember them unless you save a Layout.")

        row3 = ttk.Frame(frame)
        row3.pack(fill="x", pady=(4, 0))
        self._replay_export = tk.BooleanVar(value=False)
        export_cb = ttk.Checkbutton(row3, text="--export", variable=self._replay_export)
        export_cb.pack(side="left")
        _Tooltip(export_cb,
                  "Computes aeb_outputs for every tick (one forward pass, same\n"
                  "as always) and writes it + the recorded inputs/video into a\n"
                  "NEW .mcap, auto-named <recording>_<timestamp>.mcap under\n"
                  "tests/carla_testruns/exports/. Open THAT file directly in\n"
                  "Foxglove Studio (File > Open, not a live connection) for\n"
                  "perfectly synced native play/pause/seek/rewind - no live\n"
                  "server, no lag, since nothing is computed live anymore.\n"
                  "This is the fix for --viz's live Foxglove view looking out\n"
                  "of sync while stepping by hand.")
        open_exports_btn = ttk.Button(row3, text="Open Exports Folder",
                                       command=self._open_exports_folder)
        open_exports_btn.pack(side="left", padx=8)
        _Tooltip(open_exports_btn,
                  "Opens tests/carla_testruns/exports/ in File Explorer, so\n"
                  "you can drag the latest exported .mcap into Foxglove Studio.")

        self._replay_cmd_label = ttk.Label(frame, text="", foreground="#555",
                                            font=("Consolas", 8))
        self._replay_cmd_label.pack(anchor="w", pady=(6, 0))
        self._replay_run_status = ttk.Label(frame, text="idle", foreground="gray")
        self._replay_run_status.pack(anchor="w")

    def _refresh_recordings(self):
        self._recording_cb.config(values=_list_recordings())

    def _open_exports_folder(self):
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        os.startfile(EXPORTS_DIR)

    def _run_replay(self):
        recording = self._recording.get().strip()
        if not recording:
            self._replay_run_status.config(text="[error] No recording selected.", foreground="#c0392b")
            return
        if self._replay_viz.get() and _port_in_use(FOXGLOVE_PORT):
            self._replay_run_status.config(
                text=f"[error] port {FOXGLOVE_PORT} already in use - close the previous "
                     "--viz run's BEV window (press a key, don't just click X) and retry.",
                foreground="#c0392b")
            return
        _save_cfg(recording=recording)
        cmd = ["py", "-3.12", "df_dll_sim_mcap.py", recording]
        if self._replay_viz.get():
            cmd.append("--viz")
        if self._replay_step.get():
            cmd.append("--step")
        if self._replay_nowait.get():
            cmd.append("--no-wait")
        if self._replay_export.get():
            cmd.append("--export")
        self._replay_run_btn.config(state="disabled")
        self._replay_stop_btn.config(state="normal")
        self._replay_cmd_label.config(text="$ " + " ".join(cmd) + f"   (cwd: {REPLAY_DIR})")
        self._replay_run_status.config(text="running...", foreground="darkorange")
        self._replay_runner = _ProcessRunner(cmd, REPLAY_DIR, on_done=self._on_replay_done)
        self._replay_runner.start()

    def _stop_replay(self):
        if self._replay_runner:
            self._replay_runner.stop()

    def _on_replay_done(self, rc):
        self.root.after(0, self._replay_done_ui, rc)

    def _replay_done_ui(self, rc):
        self._replay_run_btn.config(state="normal")
        self._replay_stop_btn.config(state="disabled")
        ok = rc == 0
        self._replay_run_status.config(text=f"done (rc={rc})" if ok else f"exited rc={rc}",
                                        foreground="#2a9d2a" if ok else "#c0392b")

    def _browse_foxglove_exe(self):
        path = filedialog.askopenfilename(
            title="Select Foxglove Studio executable",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")])
        if path:
            self._foxglove_exe.set(path)
            _set_persistent_env(FOXGLOVE_EXE_ENV, path)

    def _open_foxglove(self):
        exe = self._foxglove_exe.get().strip()
        if exe and os.path.isfile(exe):
            _set_persistent_env(FOXGLOVE_EXE_ENV, exe)
            try:
                subprocess.Popen([exe])
                return
            except OSError:
                pass  # fall through to the browser tab below
        webbrowser.open("https://studio.foxglove.dev/")

    # ── PUBLISH ───────────────────────────────────────────────────────────────

    def _build_publish_section(self):
        frame = ttk.LabelFrame(self.root, text="PUBLISH (adas-local remote)", padding=8)
        frame.pack(fill="x", padx=10, pady=(4, 10))

        row1 = ttk.Frame(frame)
        row1.pack(fill="x")
        ttk.Label(row1, text="Existing versions:").pack(side="left")
        self._pub_existing = tk.StringVar()
        self._pub_existing_cb = ttk.Combobox(row1, textvariable=self._pub_existing,
                                              values=[], state="readonly", width=14)
        self._pub_existing_cb.pack(side="left", padx=4)
        ttk.Button(row1, text="↻", width=3, command=self._refresh_publish_versions).pack(
            side="left")
        self._pub_remote_status = ttk.Label(row1, text="", foreground="gray")
        self._pub_remote_status.pack(side="left", padx=(8, 0))
        _Tooltip(self._pub_existing_cb,
                  "Versions of adas-df already on the adas-local remote -\n"
                  "refreshed automatically when this GUI starts. Pick a new\n"
                  "version number below that isn't already in this list.")

        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Label(row2, text="Current (CMakeLists.txt):").pack(side="left")
        self._pub_current_label = ttk.Label(row2, text=_current_version(), foreground="#555")
        self._pub_current_label.pack(side="left", padx=(4, 12))

        ttk.Label(row2, text="New version:").pack(side="left")
        self._pub_new_version = tk.StringVar(value=_current_version())
        new_version_entry = ttk.Entry(row2, textvariable=self._pub_new_version, width=10)
        new_version_entry.pack(side="left", padx=4)
        _Tooltip(new_version_entry,
                  "Publishing rewrites this into CMakeLists.txt's\n"
                  "project(adas-df VERSION ...) line before running\n"
                  "conan create - the same line conanfile.py's set_version()\n"
                  "already reads. Bumping is a deliberate choice, not\n"
                  "automatic - pick a version not already in the list above.\n"
                  "\n"
                  "Builds EVERY project variant declared in conf/build.yml\n"
                  "(base, cus1, ...) - one conan create per variant, then a\n"
                  "single upload once all of them succeed. This is\n"
                  "deliberate: conan upload has no concept of \"did you build\n"
                  "every configuration\", so publishing only ever builds one\n"
                  "variant would silently leave the others missing on the\n"
                  "remote.")

        self._publish_btn = ttk.Button(row2, text="⬆ Publish", command=self._run_publish)
        self._publish_btn.pack(side="left", padx=(8, 4))
        self._publish_stop_btn = ttk.Button(row2, text="■ Stop", command=self._stop_publish,
                                             state="disabled")
        self._publish_stop_btn.pack(side="left")

        self._publish_cmd_label = ttk.Label(frame, text="", foreground="#555",
                                             font=("Consolas", 8))
        self._publish_cmd_label.pack(anchor="w", pady=(6, 0))
        self._publish_status = ttk.Label(frame, text="idle", foreground="gray")
        self._publish_status.pack(anchor="w")

        self._publish_runner = None
        self._refresh_publish_versions()

    def _refresh_publish_versions(self):
        # Bug #10: querying the remote used to run synchronously on the main
        # thread (measured ~14s freeze when unreachable) - now backgrounded,
        # same as every other button's _ProcessRunner pattern.
        self._pub_remote_status.config(text="checking remote...", foreground="darkorange")

        def work():
            try:
                versions = conan_publish.list_remote_versions(PACKAGE_NAME)
            except conan_publish.RemoteUnavailableError as exc:
                self.root.after(0, self._on_refresh_versions_done, None, exc)
                return
            self.root.after(0, self._on_refresh_versions_done, versions, None)

        threading.Thread(target=work, daemon=True).start()

    def _on_refresh_versions_done(self, versions, error):
        if error is not None:
            # Bug #9: "can't reach the remote / session expired" must look
            # different from a genuinely empty dropdown, not silently fold
            # into the same "nothing published yet" state.
            self._pub_existing_cb.config(values=[])
            self._pub_remote_status.config(text=f"[remote unreachable] {error}",
                                            foreground="#c0392b")
            return
        self._pub_existing_cb.config(values=versions)
        if versions:
            self._pub_existing_cb.current(len(versions) - 1)
        self._pub_remote_status.config(text="", foreground="gray")

    def _run_publish(self):
        new_version = self._pub_new_version.get().strip()
        if not new_version:
            self._publish_status.config(text="[error] Enter a version number.",
                                         foreground="#c0392b")
            return
        self._publish_btn.config(state="disabled")
        self._publish_status.config(text="checking remote...", foreground="darkorange")

        def work():
            try:
                existing = conan_publish.list_remote_versions(PACKAGE_NAME)
                if new_version in existing:
                    self.root.after(
                        0, self._publish_precheck_failed,
                        f"[error] {PACKAGE_NAME}/{new_version} already exists on the "
                        "remote - pick a different version.")
                    return
                cmds = conan_publish.publish_commands(DF_ROOT, PACKAGE_NAME, new_version)
            except conan_publish.RemoteUnavailableError as exc:
                self.root.after(0, self._publish_precheck_failed,
                                 f"[error] remote unreachable: {exc}")
                return
            except conan_publish.MissingDependencyError as exc:
                self.root.after(0, self._publish_precheck_failed, f"[error] {exc}")
                return
            self.root.after(0, self._publish_precheck_ok, cmds, new_version)

        threading.Thread(target=work, daemon=True).start()

    def _publish_precheck_failed(self, message):
        self._publish_btn.config(state="normal")
        self._publish_status.config(text=message, foreground="#c0392b")

    def _publish_precheck_ok(self, cmds, new_version):
        try:
            conan_publish.bump_cmake_version(DF_CMAKELISTS, PACKAGE_NAME, new_version)
        except (OSError, ValueError) as exc:
            self._publish_btn.config(state="normal")
            self._publish_status.config(text=f"[error] {exc}", foreground="#c0392b")
            return
        self._pub_current_label.config(text=_current_version())

        self._publish_stop_btn.config(state="normal")
        self._publish_cmd_label.config(
            text="\n".join("$ " + " ".join(c) for c in cmds) + f"   (cwd: {DF_ROOT})")
        self._publish_status.config(text="publishing...", foreground="darkorange")
        self._publish_runner = _ProcessRunner(cmds, DF_ROOT, on_done=self._on_publish_done)
        self._publish_runner.start()

    def _stop_publish(self):
        if self._publish_runner:
            self._publish_runner.stop()

    def _on_publish_done(self, rc, editable_restored=None):
        self.root.after(0, self._publish_done_ui, rc, editable_restored)

    def _publish_done_ui(self, rc, editable_restored=None):
        self._publish_btn.config(state="normal")
        self._publish_stop_btn.config(state="disabled")
        if editable_restored is True:
            self._publish_status.config(
                text="stopped - editable mode restored", foreground="#c0392b")
        elif editable_restored is False:
            self._publish_status.config(
                text="stopped before editable restore - run `conan editable add .` manually",
                foreground="#c0392b")
        else:
            ok = rc == 0
            self._publish_status.config(text=f"done (rc={rc})" if ok else f"exited rc={rc}",
                                         foreground="#2a9d2a" if ok else "#c0392b")
        self._refresh_publish_versions()


def main():
    root = tk.Tk()
    DfGuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
