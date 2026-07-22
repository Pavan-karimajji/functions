"""
modules/df/scripts/df_sim_gui.py

df-only simulator GUI - CARLA + MCAP replay/Foxglove viz. Split out of the old
df_gui.py (plan.md item 17): the build/publish half moved to the
component-agnostic scripts/build_gui.py (identical across every component),
leaving this file with only the tooling that is genuinely df-specific and
exists nowhere else. Renamed to say what it is - a simulator launcher, not a
build tool.

Pure launcher, same rules as before (docs/df_dev_gui_plan.md): every button
shells out to a command that already exists (carla_bridge.py,
df_dll_sim_mcap.py); nothing here reimplements CARLA/replay logic or edits a
YAML value - dropdowns are populated by scanning the filesystem, never
hardcoded. Subprocess output is NOT captured into the GUI - it inherits this
app's own console (the cmd window sim_gui.bat opened), so there's no in-app
log panel; buttons just show run/done state. CARLA/Foxglove exe paths are
persisted as real user-scope Windows env vars (CARLA_ROOT/FOXGLOVE_EXE via
setx), not a repo-local file - they're machine facts, not per-clone ones.

Workflow, top to bottom:
  1. CARLA                  - launch the server, run the live bridge
  2. REPLAY & FOXGLOVE VIZ  - replay a recorded .mcap, no CARLA needed

Run:
    sim_gui.bat
    (or: py df_sim_gui.py, from this folder)
"""

import json
import os
import socket
import subprocess
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, ttk

# ── paths ─────────────────────────────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))          # modules/df/scripts
DF_ROOT = os.path.dirname(_THIS_DIR)                              # modules/df

CARLA_DIR = os.path.join(DF_ROOT, "tools", "carla")
REPLAY_DIR = os.path.join(CARLA_DIR, "replay")
SCENARIOS_DIR = os.path.join(DF_ROOT, "tests", "carla_scenarios")
TESTRUNS_DIR = os.path.join(DF_ROOT, "tests", "carla_testruns")
EXPORTS_DIR = os.path.join(TESTRUNS_DIR, "exports")
GUI_CFG_PATH = os.path.join(_THIS_DIR, "df_sim_gui_config.json")

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


# ── data helpers (dropdowns - read-only, scan the filesystem, never
#    hardcoded lists) ─────────────────────────────────────────────────────────

def _list_scenarios():
    if not os.path.isdir(SCENARIOS_DIR):
        return []
    return sorted(f for f in os.listdir(SCENARIOS_DIR) if f.endswith(".yaml"))


def _list_recordings():
    if not os.path.isdir(TESTRUNS_DIR):
        return []
    return sorted(f for f in os.listdir(TESTRUNS_DIR) if f.endswith(".mcap"))


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
    """Runs a command on a background thread so the UI stays responsive. Output
    is NOT captured - the command inherits this app's own console, same window
    the user launched sim_gui.bat from. Stops early if stop() is called."""

    def __init__(self, cmd, cwd, on_done=None):
        self._cmd = cmd
        self._cwd = cwd
        self._on_done = on_done
        self._proc = None
        self._stopped = False

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stopped = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def _run(self):
        try:
            self._proc = subprocess.Popen(self._cmd, cwd=self._cwd)
            rc = self._proc.wait()
        except OSError:
            rc = -1
        if self._on_done:
            self._on_done(rc)


# ── main app ──────────────────────────────────────────────────────────────────

class DfSimGuiApp:

    def __init__(self, root):
        self.root = root
        root.title("df - Simulator (CARLA + Replay)")
        root.minsize(680, 360)

        self._cfg = _load_cfg()

        self._carla_runner = None
        self._replay_runner = None
        self._carla_proc = None  # CarlaUE4.exe handle - separate from the bridge runner

        self._build_carla_section()
        self._build_replay_section()

    # ── CARLA ─────────────────────────────────────────────────────────────────

    def _build_carla_section(self):
        frame = ttk.LabelFrame(self.root, text="CARLA", padding=8)
        frame.pack(fill="x", padx=10, pady=(10, 4))

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


def main():
    root = tk.Tk()
    DfSimGuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
