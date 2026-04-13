"""AI Provider Connection dialog for JellyRip.

Toplevel popup that lets the user:
- See all available providers and their connection status
- Enter/edit API keys
- Select models
- Test connections
- Choose the active cloud provider

Opened from Settings or the AI mode bar.  Never touches engine/ or
transcode/ — all provider logic lives in shared/ai/.
"""

from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox
from typing import Any, Callable

# Style constants matching the app's GitHub-dark theme
_BG = "#0d1117"
_BG2 = "#161b22"
_BG3 = "#21262d"
_FG = "#c9d1d9"
_FG_DIM = "#8b949e"
_ACCENT = "#58a6ff"
_GREEN = "#238636"
_GREEN_FG = "#3fb950"
_RED = "#f85149"
_YELLOW = "#d29922"
_CANCEL_BG = "#30363d"

# ── Pricing table (display-only, per 1M tokens) ──────────────────────
# Kept here in the dialog layer — never imported by engine/runtime code.
# These are point-in-time snapshots; treat as cached display data.
_PRICING_LAST_UPDATED = "2026-04"
# fmt: off
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # model_id:                         (input $/1M,  output $/1M)
    # Claude
    "claude-sonnet-4-20250514":         (3.00,   15.00),
    "claude-haiku-4-5-20251001":        (0.80,    4.00),
    "claude-opus-4-6":                  (15.00,  75.00),
    # OpenAI
    "gpt-4o":                           (2.50,   10.00),
    "gpt-4o-mini":                      (0.15,    0.60),
    "gpt-4.1-mini":                     (0.40,    1.60),
    "gpt-4.1-nano":                     (0.10,    0.40),
    # Gemini
    "gemini-2.5-flash":                 (0.15,    0.60),
    "gemini-2.0-flash":                 (0.10,    0.40),
    "gemini-2.0-flash-lite":            (0.075,   0.30),
}
# fmt: on

# Typical diagnostic call: ~1.5K input tokens, ~400 output tokens.
_TYPICAL_INPUT_TOKENS = 1500
_TYPICAL_OUTPUT_TOKENS = 400


def _format_model_cost(model_id: str) -> str | None:
    """Return a short cost string for a model, or None if unknown/free."""
    pricing = _MODEL_PRICING.get(model_id)
    if pricing is None:
        return None
    input_per_m, output_per_m = pricing
    # Estimated cost per diagnostic call
    est = (_TYPICAL_INPUT_TOKENS * input_per_m + _TYPICAL_OUTPUT_TOKENS * output_per_m) / 1_000_000
    if est < 0.001:
        est_str = "<$0.001"
    else:
        est_str = f"~${est:.4f}"
    return (
        f"${input_per_m:g} / ${output_per_m:g} per 1M tok  \u2022  {est_str}/call"
        f"  (as of {_PRICING_LAST_UPDATED})"
    )


class AIProviderDialog:
    """Modal dialog for managing AI provider connections."""

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._parent = parent
        self._on_change = on_change
        self._win: tk.Toplevel | None = None
        self._provider_frames: dict[str, dict[str, Any]] = {}

    def show(self) -> None:
        if self._win is not None and self._win.winfo_exists():
            self._win.lift()
            self._win.focus_force()
            return

        win = tk.Toplevel(self._parent)
        self._win = win
        win.title("AI Provider Setup")
        win.configure(bg=_BG)
        win.geometry("620x640")
        win.resizable(False, True)
        try:
            win.grab_set()
        except tk.TclError:
            pass
        win.lift()
        win.focus_force()
        win.transient(self._parent)

        # Header
        tk.Label(
            win, text="AI Provider Connections",
            bg=_BG, fg=_ACCENT,
            font=("Segoe UI", 14, "bold"),
        ).pack(fill="x", padx=16, pady=(14, 2))
        tk.Label(
            win,
            text="Configure which AI backends JellyRip can use for diagnostics.",
            bg=_BG, fg=_FG_DIM,
            font=("Segoe UI", 10),
        ).pack(fill="x", padx=16, pady=(0, 10))

        # Scrollable area for provider cards
        canvas = tk.Canvas(win, bg=_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        self._scroll_frame = tk.Frame(canvas, bg=_BG)
        self._scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(16, 0), pady=4)
        scrollbar.pack(side="right", fill="y", padx=(0, 4), pady=4)

        self._build_provider_cards()

        # Bottom buttons
        btn_row = tk.Frame(win, bg=_BG)
        btn_row.pack(fill="x", padx=16, pady=12)
        tk.Button(
            btn_row, text="Close",
            bg=_CANCEL_BG, fg=_FG,
            font=("Segoe UI", 10), relief="flat",
            command=self._close,
        ).pack(side="right", padx=4)

        win.protocol("WM_DELETE_WINDOW", self._close)

    def _close(self) -> None:
        if self._win:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None

    def _build_provider_cards(self) -> None:
        from shared.ai.provider_registry import get_connection_summary, list_providers

        providers = list_providers()
        summary = get_connection_summary()

        for info in providers:
            pid = info.id
            status = summary.get(pid, {})
            self._build_single_card(info, status)

    def _build_single_card(self, info: Any, status: dict[str, Any]) -> None:
        from shared.ai.credential_store import get_provider_credentials

        pid = info.id
        creds = get_provider_credentials(pid)
        frame = tk.Frame(self._scroll_frame, bg=_BG2, bd=1, relief="solid")
        frame.pack(fill="x", padx=4, pady=6, ipady=6)

        # Title row
        title_row = tk.Frame(frame, bg=_BG2)
        title_row.pack(fill="x", padx=12, pady=(8, 2))

        tk.Label(
            title_row, text=info.display_name,
            bg=_BG2, fg=_FG,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left")

        category_color = _ACCENT if info.category == "cloud" else _YELLOW
        tk.Label(
            title_row,
            text=info.category.upper(),
            bg=_BG2, fg=category_color,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(8, 0))

        # Status indicator (updated via _set_provider_status after build)
        is_active = status.get("is_active", False)
        has_creds = status.get("has_credentials", False)
        if is_active and has_creds:
            init_state = "active"
        elif has_creds:
            init_state = "connected"
        else:
            init_state = "not_connected"
        init_text, init_color = self._STATUS_MAP[init_state]

        status_label = tk.Label(
            title_row, text=init_text,
            bg=_BG2, fg=init_color,
            font=("Segoe UI", 9),
        )
        status_label.pack(side="right")

        # API key row (for cloud providers)
        widgets: dict[str, Any] = {"status_label": status_label, "frame": frame}

        if info.requires_api_key:
            key_row = tk.Frame(frame, bg=_BG2)
            key_row.pack(fill="x", padx=12, pady=2)
            tk.Label(
                key_row, text="API Key:",
                bg=_BG2, fg=_FG_DIM,
                font=("Segoe UI", 10), width=8, anchor="w",
            ).pack(side="left")
            key_var = tk.StringVar(value=creds.get("api_key", ""))
            key_entry = tk.Entry(
                key_row, textvariable=key_var,
                bg=_BG, fg=_FG,
                font=("Consolas", 10),
                insertbackground="white",
                relief="flat", bd=3, width=42, show="*",
            )
            key_entry.pack(side="left", padx=4)
            # Toggle show/hide
            show_var = tk.BooleanVar(value=False)

            def _toggle_show(entry: tk.Entry = key_entry, sv: tk.BooleanVar = show_var) -> None:
                sv.set(not sv.get())
                entry.configure(show="" if sv.get() else "*")

            tk.Button(
                key_row, text="Show",
                bg=_BG3, fg=_FG_DIM,
                font=("Segoe UI", 8), relief="flat",
                command=_toggle_show,
            ).pack(side="left", padx=2)
            widgets["key_var"] = key_var

            # Security indicator (shows when a key is saved)
            if has_creds:
                from shared.ai.credential_store import is_encrypted_storage
                security_row = tk.Frame(frame, bg=_BG2)
                security_row.pack(fill="x", padx=12, pady=(0, 2))
                if is_encrypted_storage():
                    sec_text = "\U0001f512 Stored securely (Windows encrypted)"
                    sec_color = _GREEN_FG
                else:
                    sec_text = "\U0001f513 Stored locally (plaintext)"
                    sec_color = _YELLOW
                security_label = tk.Label(
                    security_row, text=sec_text,
                    bg=_BG2, fg=sec_color,
                    font=("Segoe UI", 9),
                )
                security_label.pack(side="left", padx=(64, 0))
                widgets["security_label"] = security_label
        else:
            # Local provider: base URL
            url_row = tk.Frame(frame, bg=_BG2)
            url_row.pack(fill="x", padx=12, pady=2)
            tk.Label(
                url_row, text="URL:",
                bg=_BG2, fg=_FG_DIM,
                font=("Segoe UI", 10), width=8, anchor="w",
            ).pack(side="left")
            url_var = tk.StringVar(
                value=creds.get("base_url", "http://localhost:11434")
            )
            tk.Entry(
                url_row, textvariable=url_var,
                bg=_BG, fg=_FG,
                font=("Consolas", 10),
                insertbackground="white",
                relief="flat", bd=3, width=42,
            ).pack(side="left", padx=4)
            widgets["url_var"] = url_var

        # Model selector
        model_row = tk.Frame(frame, bg=_BG2)
        model_row.pack(fill="x", padx=12, pady=2)
        tk.Label(
            model_row, text="Model:",
            bg=_BG2, fg=_FG_DIM,
            font=("Segoe UI", 10), width=8, anchor="w",
        ).pack(side="left")
        current_model = creds.get("model", info.default_model)
        model_var = tk.StringVar(value=current_model)
        model_menu = tk.OptionMenu(model_row, model_var, *info.available_models)
        model_menu.configure(
            bg=_BG, fg=_FG, font=("Segoe UI", 10),
            highlightthickness=0, relief="flat",
            activebackground=_BG3, activeforeground=_FG,
        )
        model_menu["menu"].configure(
            bg=_BG2, fg=_FG, font=("Segoe UI", 10),
            activebackground=_ACCENT, activeforeground="white",
        )
        model_menu.pack(side="left", padx=4)
        widgets["model_var"] = model_var

        # Pricing label (cloud providers only)
        if info.category == "cloud":
            cost_var = tk.StringVar(value="")
            cost_label = tk.Label(
                model_row, textvariable=cost_var,
                bg=_BG2, fg=_FG_DIM,
                font=("Segoe UI", 8),
            )
            cost_label.pack(side="left", padx=(6, 0))
            widgets["cost_var"] = cost_var

            def _on_model_change(*_args: Any, cv: tk.StringVar = cost_var,
                                 mv: tk.StringVar = model_var) -> None:
                text = _format_model_cost(mv.get()) or ""
                cv.set(text)

            model_var.trace_add("write", _on_model_change)
            # Set initial value
            _on_model_change()

        # Action buttons
        btn_row = tk.Frame(frame, bg=_BG2)
        btn_row.pack(fill="x", padx=12, pady=(6, 4))

        # Detail line shown below status dot (latency, error excerpt, etc.)
        detail_var = tk.StringVar(value="")
        detail_label = tk.Label(
            btn_row, textvariable=detail_var,
            bg=_BG2, fg=_FG_DIM,
            font=("Segoe UI", 8),
        )
        detail_label.pack(side="right", padx=4)
        widgets["detail_var"] = detail_var
        widgets["detail_label"] = detail_label

        tk.Button(
            btn_row, text="Test",
            bg=_BG3, fg=_FG,
            font=("Segoe UI", 9), relief="flat",
            command=lambda p=pid: self._test_provider(p),
        ).pack(side="left", padx=(0, 4))

        tk.Button(
            btn_row, text="Save",
            bg=_GREEN, fg="white",
            font=("Segoe UI", 9, "bold"), relief="flat",
            command=lambda p=pid: self._save_provider(p),
        ).pack(side="left", padx=(0, 4))

        if info.category == "cloud":
            set_active_btn = tk.Button(
                btn_row, text="Set as Active",
                bg=_ACCENT if not status.get("is_active") else _BG3,
                fg="white" if not status.get("is_active") else _GREEN_FG,
                font=("Segoe UI", 9, "bold"), relief="flat",
                command=lambda p=pid: self._set_active(p),
            )
            set_active_btn.pack(side="left", padx=(0, 4))
            widgets["set_active_btn"] = set_active_btn

        # Disconnect button (only shown when credentials exist)
        if has_creds:
            tk.Button(
                btn_row, text="Disconnect",
                bg=_CANCEL_BG, fg=_RED,
                font=("Segoe UI", 9), relief="flat",
                command=lambda p=pid: self._disconnect_provider(p),
            ).pack(side="left", padx=(0, 4))

        # Help link — opens provider page and nudges the user back to paste + validate
        if info.help_url:
            link_text = "Get API key \u2192" if info.requires_api_key else "Setup guide \u2192"
            help_label = tk.Label(
                btn_row,
                text=link_text,
                bg=_BG2, fg=_ACCENT,
                font=("Segoe UI", 9, "underline"),
                cursor="hand2",
            )
            help_label.pack(side="right", padx=4)
            help_label.bind(
                "<Button-1>",
                lambda _e, p=pid, url=info.help_url: self._open_setup_guide(p, url),
            )

        self._provider_frames[pid] = widgets

    def _open_setup_guide(self, pid: str, url: str) -> None:
        """Open the provider's key-management page and show an inline prompt."""
        webbrowser.open(url)
        widgets = self._provider_frames.get(pid, {})

        # Focus the API key entry so the user can paste immediately
        key_entry = self._find_key_entry(pid)
        if key_entry:
            key_entry.focus_set()
            # Un-mask the field briefly so the user sees what they paste
            key_entry.configure(show="")

        # Show a transient inline hint below the action row
        frame = widgets.get("frame")
        if not frame:
            return

        # Avoid stacking duplicate hints
        existing = getattr(self, "_setup_hints", {})
        if pid in existing:
            try:
                existing[pid].destroy()
            except Exception:
                pass

        hint = tk.Frame(frame, bg=_BG3)
        hint.pack(fill="x", padx=12, pady=(2, 6))

        has_key = "key_var" in widgets
        hint_text = (
            "\U0001f310  Browser opened \u2014 copy your key, paste it above, then hit"
            if has_key
            else "\U0001f310  Browser opened \u2014 once installed, hit"
        )
        tk.Label(
            hint, text=hint_text,
            bg=_BG3, fg=_FG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(8, 0), pady=4)

        validate_btn = tk.Button(
            hint, text="Save & Test",
            bg=_GREEN, fg="white",
            font=("Segoe UI", 9, "bold"), relief="flat",
            command=lambda p=pid: self._save_and_test(p),
        )
        validate_btn.pack(side="left", padx=(6, 4), pady=4)

        dismiss = tk.Label(
            hint, text="\u2715",
            bg=_BG3, fg=_FG_DIM,
            font=("Segoe UI", 10),
            cursor="hand2",
        )
        dismiss.pack(side="right", padx=(0, 6), pady=4)
        dismiss.bind("<Button-1>", lambda _e: hint.destroy())

        if not hasattr(self, "_setup_hints"):
            self._setup_hints: dict[str, tk.Frame] = {}
        self._setup_hints[pid] = hint

    def _find_key_entry(self, pid: str) -> tk.Entry | None:
        """Locate the API-key Entry widget inside a provider card."""
        widgets = self._provider_frames.get(pid, {})
        frame = widgets.get("frame")
        if not frame:
            return None
        for child in frame.winfo_children():
            for sub in child.winfo_children():
                if isinstance(sub, tk.Entry):
                    try:
                        if sub.cget("show") in ("*", ""):
                            return sub
                    except Exception:
                        pass
        return None

    def _save_and_test(self, pid: str) -> None:
        """Convenience: save credentials (which auto-validates) and clean up the hint."""
        self._save_provider(pid)
        # Re-mask the key entry after save
        key_entry = self._find_key_entry(pid)
        if key_entry:
            key_entry.configure(show="*")
        # Remove the setup hint
        hints = getattr(self, "_setup_hints", {})
        hint = hints.pop(pid, None)
        if hint:
            try:
                hint.destroy()
            except Exception:
                pass

    def _collect_provider_kwargs(self, pid: str) -> dict[str, str]:
        """Collect current field values for a provider."""
        widgets = self._provider_frames.get(pid, {})
        kwargs: dict[str, str] = {}
        if "key_var" in widgets:
            kwargs["api_key"] = widgets["key_var"].get().strip()
        if "url_var" in widgets:
            kwargs["base_url"] = widgets["url_var"].get().strip()
        if "model_var" in widgets:
            kwargs["model"] = widgets["model_var"].get().strip()
        return kwargs

    def _save_provider(self, pid: str) -> None:
        """Save credentials, then auto-validate the connection."""
        from shared.ai.credential_store import set_provider_credentials

        kwargs = self._collect_provider_kwargs(pid)
        try:
            set_provider_credentials(pid, **kwargs)
            if self._on_change:
                self._on_change()
        except Exception as e:
            self._set_provider_status(pid, "failed", detail=f"Save error: {e}")
            return

        # Auto-validate: kick off a lightweight test immediately
        self._test_provider(pid)

    def _test_provider(self, pid: str) -> None:
        """Test connection in a background thread."""
        from shared.ai.provider_registry import get_provider

        kwargs = self._collect_provider_kwargs(pid)
        provider = get_provider(pid)
        if not provider:
            self._set_provider_status(pid, "failed", detail="Unknown provider")
            return

        # Apply current (unsaved) values for the test
        provider.configure(**kwargs)
        self._set_provider_status(pid, "validating")

        def _run() -> None:
            result = provider.test_connection(timeout=15.0)
            if self._win and self._win.winfo_exists():
                self._win.after(0, lambda: self._handle_test_result(pid, result))

        threading.Thread(target=_run, daemon=True).start()

    def _handle_test_result(self, pid: str, result: Any) -> None:
        from shared.ai.credential_store import get_active_provider_id

        if result.success:
            is_active = get_active_provider_id() == pid
            state = "active" if is_active else "connected"
            self._set_provider_status(
                pid, state,
                detail=f"{result.latency_ms:.0f}ms \u2022 {result.model_confirmed}",
            )
        else:
            self._set_provider_status(
                pid, "failed",
                detail=result.error[:80],
            )

    def _set_active(self, pid: str) -> None:
        """Set this provider as the active cloud provider."""
        from shared.ai.credential_store import set_active_provider_id

        set_active_provider_id(pid)

        # Promote this card to "active", demote others to "connected"
        for other_pid, widgets in self._provider_frames.items():
            set_btn = widgets.get("set_active_btn")
            if other_pid == pid:
                self._set_provider_status(pid, "active")
                if set_btn:
                    set_btn.configure(bg=_BG3, fg=_GREEN_FG)
            else:
                if set_btn:
                    set_btn.configure(bg=_ACCENT, fg="white")
                # Demote from "active" to "connected" (only if it had creds)
                creds_ok = bool(self._collect_provider_kwargs(other_pid).get("api_key"))
                if widgets.get("key_var"):
                    if creds_ok:
                        self._set_provider_status(other_pid, "connected")
                    else:
                        self._set_provider_status(other_pid, "not_connected")

        if self._on_change:
            self._on_change()

    def _disconnect_provider(self, pid: str) -> None:
        """Remove saved credentials for a provider after confirmation."""
        from shared.ai.credential_store import (
            get_active_provider_id,
            remove_provider_credentials,
            set_active_provider_id,
        )
        from shared.ai.provider_registry import get_provider

        provider = get_provider(pid)
        name = provider.info().display_name if provider else pid

        if not messagebox.askyesno(
            "Disconnect Provider",
            f"Remove the saved API key for {name}?\n\n"
            "You can re-enter it at any time.",
            parent=self._win,
        ):
            return

        remove_provider_credentials(pid)

        # If this was the active provider, clear active selection
        if get_active_provider_id() == pid:
            set_active_provider_id("")

        # Clear the key field in the UI
        widgets = self._provider_frames.get(pid, {})
        key_var = widgets.get("key_var")
        if key_var:
            key_var.set("")

        self._set_provider_status(pid, "not_connected")

        # Remove the security indicator if present
        sec_label = widgets.get("security_label")
        if sec_label:
            try:
                sec_label.master.destroy()
            except Exception:
                pass
            widgets.pop("security_label", None)

        if self._on_change:
            self._on_change()

    # ── Unified status state machine ────────────────────────────────────
    # Every provider card shows exactly one state at all times.
    #   active        — green dot, "Active"       (chosen cloud provider)
    #   connected     — green dot, "Connected"     (credentials saved + validated)
    #   validating    — yellow dot, "Validating…"  (test in progress)
    #   failed        — red dot, "Failed"          (test or save error)
    #   not_connected — dim dot, "Not connected"   (no credentials)

    _STATUS_MAP: dict[str, tuple[str, str]] = {
        "active":        ("\u25cf Active",        _GREEN_FG),
        "connected":     ("\u25cf Connected",     _GREEN_FG),
        "validating":    ("\u25cf Validating\u2026", _YELLOW),
        "failed":        ("\u25cf Failed",        _RED),
        "not_connected": ("\u25cf Not connected", _FG_DIM),
    }

    def _set_provider_status(
        self, pid: str, state: str, *, detail: str = "",
    ) -> None:
        """Set the single canonical status for a provider card."""
        if not (self._win and self._win.winfo_exists()):
            return
        widgets = self._provider_frames.get(pid, {})
        label = widgets.get("status_label")
        text, color = self._STATUS_MAP.get(state, self._STATUS_MAP["not_connected"])
        if label:
            label.configure(text=text, fg=color)
        # Detail line (latency, error excerpt, or blank)
        detail_var = widgets.get("detail_var")
        detail_label = widgets.get("detail_label")
        if detail_var:
            detail_var.set(detail)
        if detail_label:
            detail_color = _FG_DIM if state != "failed" else _RED
            detail_label.configure(fg=detail_color)


def open_ai_provider_dialog(
    parent: tk.Tk | tk.Toplevel,
    on_change: Callable[[], None] | None = None,
) -> None:
    """Convenience entry point to open the AI provider dialog."""
    dialog = AIProviderDialog(parent, on_change=on_change)
    dialog.show()
