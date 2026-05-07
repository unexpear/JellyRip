// JellyRipMock — recreates the actual JellyRip layout from gui/main_window.py
// (header → drive row → primary buttons → secondary buttons → utility row →
// progress + status → log panel + input bar). Themed via CSS variables.

const { useState } = React;

function JellyRipMock({ theme }) {
  const t = theme.tokens;
  const [drive, setDrive] = useState("BD-RE  /  HL-DT-ST BD-RE BU40N  (E:)");
  const [progress] = useState(64);
  const [inputVal, setInputVal] = useState("");

  return (
    <div
      className="jr-window"
      data-family={theme.family}
      style={{
        "--bg":        t.bg,
        "--card":      t.card,
        "--input":     t.input,
        "--border":    t.border,
        "--fg":        t.fg,
        "--muted":     t.muted,
        "--accent":    t.accent,
        "--go":        t.go,
        "--goFg":      t.goFg,
        "--info":      t.info,
        "--infoFg":    t.infoFg,
        "--alt":       t.alt,
        "--altFg":     t.altFg,
        "--warn":      t.warn,
        "--warnFg":    t.warnFg,
        "--danger":    t.danger,
        "--dangerFg":  t.dangerFg,
        "--hover":     t.hover,
        "--selection": t.selection,
        "--logBg":     t.logBg,
        "--promptFg":  t.promptFg,
        "--answerFg":  t.answerFg,
        "--shadow":    t.shadow,
      }}
    >
      {/* Title bar — Qt window chrome */}
      <div className="jr-titlebar">
        <div className="jr-titlebar-dots">
          <span className="dot dot-r" /><span className="dot dot-y" /><span className="dot dot-g" />
        </div>
        <div className="jr-titlebar-title">JellyRip — PySide6  ·  {theme.name}</div>
        <div className="jr-titlebar-spacer" />
      </div>

      {/* Header — APP_DISPLAY_NAME on card bg, accent color */}
      <div className="jr-header">
        <div className="jr-header-title">JellyRip</div>
        <span className="jr-header-sub">PySide6  ·  {theme.id}.qss</span>
      </div>

      {/* Drive row */}
      <div className="jr-drive-row">
        <span className="jr-drive-label">Drive:</span>
        <div className="jr-combo">
          <span>{drive}</span>
          <span className="jr-combo-arrow">▾</span>
        </div>
        <button className="jr-drive-refresh" aria-label="Refresh drive list" title="Refresh">↻</button>
      </div>

      {/* Utility row — sub-row under drive, before action buttons */}
      <div className="jr-util-row">
        <button className="jr-util-btn">⚙  Settings</button>
        <button className="jr-util-btn">⇡  Check Updates</button>
        <button className="jr-util-btn">⎘  Copy Log</button>
        <button className="jr-util-btn">→  Browse Folder</button>
      </div>

      {/* Primary button row — green/green/blue */}
      <div className="jr-button-row">
        <button className="jr-mode-btn jr-go">📀  Rip TV Show Disc</button>
        <button className="jr-mode-btn jr-go">🎬  Rip Movie Disc</button>
        <button className="jr-mode-btn jr-info">💾  Dump All Titles</button>
      </div>

      {/* Secondary button row — purple/amber */}
      <div className="jr-button-row jr-button-row-secondary">
        <button className="jr-mode-btn jr-alt">📁  Organize Existing MKVs</button>
        <button className="jr-mode-btn jr-warn">🧰  Prep MKVs For FFmpeg / HandBrake</button>
      </div>

      {/* Progress bar */}
      <div className="jr-progress">
        <div className="jr-progress-fill" style={{ width: progress + "%" }} />
      </div>

      {/* Status row — italic accent + monospace meta */}
      <div className="jr-status-row">
        <span className="jr-status">Ripping Title 02  ·  64 % complete</span>
        <span className="jr-status-meta">3 of 6  ·  ETA 04:18</span>
      </div>

      {/* Stop session row */}
      <div className="jr-session-row">
        <button className="jr-stop-btn">Stop Session</button>
      </div>

      {/* Log panel */}
      <div className="jr-log-panel">
        <div className="jr-log-head">
          <span className="jr-log-label">Live Log</span>
          <span className="jr-log-led">streaming</span>
        </div>
        <div className="jr-log">
          <div className="jr-log-line">[12:04:01]  MakeMKV  v1.18.1  initialized</div>
          <div className="jr-log-line jr-log-muted">[12:04:02]  Scanning drive E:  …</div>
          <div className="jr-log-line">[12:04:09]  Disc detected: BREAKING BAD S03 D2</div>
          <div className="jr-log-line jr-log-muted">[12:04:09]  6 titles, 4 candidates after filtering</div>
          <div className="jr-log-line jr-log-answer">[12:04:14]  ✓  Title 00  →  S03E04.mkv  (44 min, 4.1 GB)</div>
          <div className="jr-log-line jr-log-answer">[12:04:48]  ✓  Title 01  →  S03E05.mkv  (47 min, 4.4 GB)</div>
          <div className="jr-log-line jr-log-prompt">[12:05:12]  ?  Title 02 has unusual chapter spacing — keep it? (y/n)</div>
          <div className="jr-log-line jr-log-muted">[12:05:13]  Awaiting confirmation  …</div>
        </div>
      </div>

      {/* Input bar — appears under log when prompt is open */}
      <div className="jr-input-bar">
        <span className="jr-input-label">Keep Title 02?</span>
        <input
          className="jr-input-field"
          value={inputVal}
          onChange={e => setInputVal(e.target.value)}
          placeholder="y / n"
        />
        <button className="jr-input-confirm">Confirm</button>
        <button className="jr-input-skip">Skip</button>
      </div>
    </div>
  );
}

window.JellyRipMock = JellyRipMock;
