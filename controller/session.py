import os
import json
import time
from datetime import datetime
from .controller import SessionState

class SessionHelpers:
    def __init__(self, controller):
        self.controller = controller

    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full = f"[{timestamp}] {msg}"
        self.controller.session_log.append(full)
        cap  = int(self.controller.engine.cfg.get("opt_log_cap_lines", 300000))
        trim = int(self.controller.engine.cfg.get("opt_log_trim_lines", 200000))
        if len(self.controller.session_log) > cap:
            self.controller.session_log = self.controller.session_log[-trim:]
        self.controller.gui.append_log(full)

    def report(self, msg):
        self.controller.session_report.append(msg)
        self.log(msg)

    def flush_log(self):
        log_file = os.path.normpath(
            self.controller.engine.cfg.get("log_file", "")
        )
        if log_file and not log_file.lower().endswith((".txt", ".log")):
            log_file = log_file + ".txt"
        self.controller.engine.write_session_log(
            log_file, self.controller.start_time, self.controller.session_log, self.log
        )

    def write_session_summary(self):
        if not self.controller.engine.cfg.get(
            "opt_session_failure_report", True
        ):
            return
        sm = getattr(self.controller, "sm", None)
        if sm is not None:
            if sm.state == SessionState.COMPLETED:
                if self.controller.session_report:
                    self.log("Session summary: Completed with warnings.")
                    self.log("=" * 44)
                    self.log("SESSION SUMMARY — WARNINGS")
                    self.log("=" * 44)
                    for line in self.controller.session_report:
                        self.log(f"  {line}")
                    self.log("=" * 44)
                else:
                    self.log(
                        "Session summary: All discs completed successfully."
                    )
                return
            if sm.state == SessionState.FAILED and not self.controller.session_report:
                self.log("Session summary: Session failed.")
                return
        if not self.controller.session_report:
            self.log(
                "Session summary: All discs completed successfully."
            )
            return
        self.log("=" * 44)
        self.log("SESSION SUMMARY — FAILURES/WARNINGS")
        self.log("=" * 44)
        for line in self.controller.session_report:
            self.log(f"  {line}")
        self.log("=" * 44)

    def scan_with_retry(self):
        for attempt in range(3):
            self.log(
                f"Scanning disc on drive "
                f"{self.controller.engine.get_disc_target()}..."
            )
            self.controller.gui.set_status("Scanning... (time varies by disc)")
            self.controller.gui.start_indeterminate()
            try:
                result = self.controller.engine.scan_disc(
                    self.log, self.controller.gui.set_progress
                )
            finally:
                self.controller.gui.stop_indeterminate()
                self.controller.gui.set_progress(0)

            if self.controller.engine.abort_event.is_set():
                self.log("Scan aborted.")
                return None

            if result is None:
                if attempt < 2:
                    self.log("Scan failed — retrying...")
                    time.sleep(2 + attempt)
                continue
            return result
        self.log("Scan failed after 3 attempts.")
        return None

    def check_resume(self, temp_root, media_type=None):
        resumable = self.controller.engine.find_resumable_sessions(temp_root)
        if not resumable:
            return None
        for full_path, name, meta, file_count in resumable:
            if media_type and meta.get("media_type") not in {None, media_type}:
                continue
            title = meta.get("title", "Unknown")
            ts    = meta.get("timestamp", name)
            phase = meta.get("phase", meta.get("status", "unknown"))
            if self.controller.gui.ask_yesno(
                f"Resume previous session?\n\n"
                f"Title: {title}\n"
                f"Started: {ts}\n"
                f"Phase: {phase}\n"
                f"Files so far: {file_count}\n\n"
                "This reloads saved workflow metadata only. Any partial "
                "rip files will be replaced by a fresh rip."
            ):
                self.log(f"Resuming session: {name}")
                return {
                    "path": full_path,
                    "name": name,
                    "meta": meta,
                }
        return None
