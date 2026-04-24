import React, { useEffect, useMemo, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

const C = {
  bg: "#0A0D14",
  surface: "#111622",
  border: "#1E2740",
  accent: "#3B82F6",
  accentHi: "#60A5FA",
  danger: "#EF4444",
  success: "#22C55E",
  warn: "#F59E0B",
  text: "#E2E8F0",
  muted: "#64748B",
};

const EMPTY_SCHEME = {
  name: "",
  description: "",
  min_income: 0,
  max_income: 999999999,
  gender: "All",
  location: "All",
  occupation: "All",
  min_age: 0,
  max_age: 120,
  benefit: "",
  active: true,
};

const styles = {
  root: {
    fontFamily: "'DM Mono', 'Courier New', monospace",
    background: "radial-gradient(circle at top, #162038 0%, #0A0D14 50%)",
    minHeight: "100vh",
    color: C.text,
  },
  header: {
    background: "rgba(17, 22, 34, 0.9)",
    borderBottom: `1px solid ${C.border}`,
    padding: "20px 32px",
    display: "flex",
    alignItems: "center",
    gap: "16px",
    position: "sticky",
    top: 0,
    backdropFilter: "blur(8px)",
    zIndex: 10,
  },
  badge: {
    background: C.accent,
    color: "#fff",
    fontSize: "10px",
    fontWeight: "700",
    letterSpacing: "2px",
    padding: "4px 8px",
    borderRadius: "4px",
  },
  title: {
    fontSize: "16px",
    fontWeight: "700",
    letterSpacing: "1px",
    color: C.text,
    margin: 0,
  },
  subtitle: { fontSize: "11px", color: C.muted, margin: 0, letterSpacing: "0.5px" },
  tabs: {
    display: "flex",
    gap: 12,
    padding: "20px 32px 0",
    flexWrap: "wrap",
  },
  tab: (active) => ({
    padding: "12px 16px",
    fontSize: "11px",
    fontWeight: "700",
    letterSpacing: "1.5px",
    textTransform: "uppercase",
    cursor: "pointer",
    borderRadius: "999px",
    border: `1px solid ${active ? C.accentHi : C.border}`,
    background: active ? `${C.accent}22` : "transparent",
    color: active ? C.accentHi : C.muted,
  }),
  body: {
    padding: "28px 32px 40px",
    maxWidth: "1120px",
    margin: "0 auto",
  },
  card: {
    background: "rgba(17, 22, 34, 0.92)",
    border: `1px solid ${C.border}`,
    borderRadius: "12px",
    padding: "24px",
    marginBottom: "16px",
    boxShadow: "0 20px 50px rgba(0,0,0,0.25)",
  },
  label: {
    display: "block",
    fontSize: "10px",
    fontWeight: "700",
    letterSpacing: "2px",
    color: C.muted,
    textTransform: "uppercase",
    marginBottom: "6px",
  },
  input: {
    width: "100%",
    background: C.bg,
    border: `1px solid ${C.border}`,
    borderRadius: "8px",
    padding: "10px 12px",
    color: C.text,
    fontSize: "13px",
    fontFamily: "inherit",
    boxSizing: "border-box",
  },
  textarea: {
    width: "100%",
    minHeight: "90px",
    background: C.bg,
    border: `1px solid ${C.border}`,
    borderRadius: "8px",
    padding: "10px 12px",
    color: C.text,
    fontSize: "13px",
    fontFamily: "inherit",
    boxSizing: "border-box",
  },
  select: {
    width: "100%",
    background: C.bg,
    border: `1px solid ${C.border}`,
    borderRadius: "8px",
    padding: "10px 12px",
    color: C.text,
    fontSize: "13px",
    fontFamily: "inherit",
    boxSizing: "border-box",
  },
  row: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "14px" },
  row3: { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "16px", marginBottom: "14px" },
  btn: (color = C.accent, outline = false) => ({
    background: outline ? "transparent" : color,
    color: outline ? color : "#fff",
    border: `1px solid ${color}`,
    borderRadius: "8px",
    padding: "10px 16px",
    fontSize: "11px",
    fontWeight: "700",
    letterSpacing: "1.5px",
    textTransform: "uppercase",
    cursor: "pointer",
    fontFamily: "inherit",
  }),
  schemeLine: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "14px 16px",
    background: C.bg,
    border: `1px solid ${C.border}`,
    borderRadius: "10px",
    marginBottom: "8px",
    gap: "12px",
  },
  chip: (color) => ({
    background: `${color}22`,
    color,
    border: `1px solid ${color}44`,
    borderRadius: "999px",
    fontSize: "10px",
    fontWeight: "700",
    padding: "4px 8px",
    letterSpacing: "1px",
  }),
  log: {
    background: C.bg,
    border: `1px solid ${C.border}`,
    borderRadius: "8px",
    padding: "14px 16px",
    fontSize: "11px",
    color: C.muted,
    lineHeight: "1.8",
    maxHeight: "240px",
    overflowY: "auto",
  },
  sqlBox: {
    background: "#0D1117",
    border: `1px solid ${C.border}`,
    borderRadius: "8px",
    padding: "16px",
    fontSize: "11px",
    color: "#7EE787",
    lineHeight: "1.8",
    overflowX: "auto",
    whiteSpace: "pre-wrap",
  },
  notice: (color) => ({
    border: `1px solid ${color}55`,
    background: `${color}11`,
    color,
    padding: "12px 14px",
    borderRadius: "10px",
    fontSize: "12px",
    marginBottom: "16px",
  }),
};

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || body.error || `Request failed: ${response.status}`);
  }
  return body;
}

function toINR(value) {
  if (value === null || value === undefined || value === "") {
    return "NA";
  }
  return `Rs ${Number(value).toLocaleString("en-IN")}`;
}

function buildSQL(scheme, schemeId = null, deactivate = false) {
  if (deactivate && schemeId !== null) {
    return `UPDATE schemes SET is_active = FALSE WHERE scheme_id = ${schemeId};`;
  }

  const description = (scheme.description || "").replace(/'/g, "''");
  if (schemeId !== null) {
    return `UPDATE schemes SET
  scheme_name = '${scheme.name.replace(/'/g, "''")}',
  description = '${description}',
  min_income = ${scheme.min_income},
  max_income = ${scheme.max_income},
  eligible_gender = '${scheme.gender}',
  eligible_location = '${scheme.location}',
  eligible_occupation = '${scheme.occupation}',
  min_age = ${scheme.min_age},
  max_age = ${scheme.max_age},
  benefit_amount = ${scheme.benefit === "" ? "NULL" : scheme.benefit},
  is_active = ${scheme.active ? "TRUE" : "FALSE"}
WHERE scheme_id = ${schemeId};`;
  }

  return `INSERT INTO schemes (
  scheme_name, description, min_income, max_income, eligible_gender,
  eligible_location, eligible_occupation, min_age, max_age, benefit_amount, is_active
) VALUES (
  '${scheme.name.replace(/'/g, "''")}',
  '${description}',
  ${scheme.min_income},
  ${scheme.max_income},
  '${scheme.gender}',
  '${scheme.location}',
  '${scheme.occupation}',
  ${scheme.min_age},
  ${scheme.max_age},
  ${scheme.benefit === "" ? "NULL" : scheme.benefit},
  ${scheme.active ? "TRUE" : "FALSE"}
);`;
}

function normalizeScheme(input) {
  return {
    ...EMPTY_SCHEME,
    ...input,
    benefit: input?.benefit ?? "",
  };
}

function useLogs() {
  const [entries, setEntries] = useState([]);
  const push = (message, color = C.muted) =>
    setEntries((current) => [...current, { message, color, time: new Date().toLocaleTimeString() }]);
  return [entries, push, setEntries];
}

function UploadPanel({ onCreated, pushLog }) {
  const fileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function extract(fileToParse) {
    setBusy(true);
    setError("");
    setFile(fileToParse);
    pushLog(`Uploading ${fileToParse.name} to the backend parser.`, C.accentHi);

    try {
      const formData = new FormData();
      formData.append("file", fileToParse);
      const data = await api("/admin/schemes/extract", { method: "POST", body: formData });
      setDraft(normalizeScheme(data.parsed));
      pushLog(`Draft extracted for ${data.parsed.name}.`, C.success);
    } catch (err) {
      setError(err.message);
      pushLog(`Extraction failed: ${err.message}`, C.danger);
    } finally {
      setBusy(false);
    }
  }

  async function createScheme() {
    if (!draft) return;
    setBusy(true);
    setError("");

    try {
      const payload = { ...draft, benefit: draft.benefit === "" ? null : Number(draft.benefit) };
      const data = await api("/admin/schemes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      pushLog(`Scheme ${data.scheme.name} saved to PostgreSQL.`, C.success);
      onCreated(data.scheme);
      setDraft(null);
      setFile(null);
    } catch (err) {
      setError(err.message);
      pushLog(`Save failed: ${err.message}`, C.danger);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div style={{ marginBottom: "12px" }}>
        <span style={styles.chip(C.accent)}>Feature 1</span>
        <span style={{ marginLeft: "10px", fontSize: "13px", fontWeight: "700" }}>Upload Policy File</span>
      </div>

      <div style={styles.card}>
        <div style={styles.row}>
          <div>
            <label style={styles.label}>Supported Files</label>
            <div style={{ ...styles.notice(C.accentHi), marginBottom: 0 }}>
              Upload a PDF or TXT file. The backend extracts text and builds a draft scheme payload.
            </div>
          </div>
          <div>
            <label style={styles.label}>Selected File</label>
            <div style={{ ...styles.notice(C.warn), marginBottom: 0 }}>
              {file ? file.name : "No file selected yet"}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
          <button style={styles.btn()} onClick={() => fileRef.current?.click()} disabled={busy}>
            Choose File
          </button>
          {file && (
            <button style={styles.btn(C.accentHi, true)} onClick={() => extract(file)} disabled={busy}>
              Re-run Extraction
            </button>
          )}
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.txt"
            style={{ display: "none" }}
            onChange={(event) => {
              const chosen = event.target.files?.[0];
              if (chosen) {
                extract(chosen);
              }
            }}
          />
        </div>

        {error && <div style={{ ...styles.notice(C.danger), marginTop: "16px" }}>{error}</div>}
      </div>

      {draft && (
        <div style={styles.card}>
          <div style={{ ...styles.label, color: C.success, marginBottom: "16px" }}>Review Draft Before Saving</div>
          <div style={{ marginBottom: "14px" }}>
            <label style={styles.label}>Scheme Name</label>
            <input style={styles.input} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          </div>
          <div style={{ marginBottom: "14px" }}>
            <label style={styles.label}>Description</label>
            <textarea style={styles.textarea} value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
          </div>
          <div style={styles.row}>
            <div>
              <label style={styles.label}>Min Income</label>
              <input style={styles.input} type="number" value={draft.min_income} onChange={(e) => setDraft({ ...draft, min_income: Number(e.target.value) })} />
            </div>
            <div>
              <label style={styles.label}>Max Income</label>
              <input style={styles.input} type="number" value={draft.max_income} onChange={(e) => setDraft({ ...draft, max_income: Number(e.target.value) })} />
            </div>
          </div>
          <div style={styles.row3}>
            <div>
              <label style={styles.label}>Gender</label>
              <select style={styles.select} value={draft.gender} onChange={(e) => setDraft({ ...draft, gender: e.target.value })}>
                <option>All</option>
                <option>Male</option>
                <option>Female</option>
              </select>
            </div>
            <div>
              <label style={styles.label}>Location</label>
              <input style={styles.input} value={draft.location} onChange={(e) => setDraft({ ...draft, location: e.target.value })} />
            </div>
            <div>
              <label style={styles.label}>Occupation</label>
              <input style={styles.input} value={draft.occupation} onChange={(e) => setDraft({ ...draft, occupation: e.target.value })} />
            </div>
          </div>
          <div style={styles.row}>
            <div>
              <label style={styles.label}>Min Age</label>
              <input style={styles.input} type="number" value={draft.min_age} onChange={(e) => setDraft({ ...draft, min_age: Number(e.target.value) })} />
            </div>
            <div>
              <label style={styles.label}>Max Age</label>
              <input style={styles.input} type="number" value={draft.max_age} onChange={(e) => setDraft({ ...draft, max_age: Number(e.target.value) })} />
            </div>
          </div>
          <div style={{ marginBottom: "14px" }}>
            <label style={styles.label}>Benefit Amount</label>
            <input style={styles.input} type="number" value={draft.benefit} onChange={(e) => setDraft({ ...draft, benefit: e.target.value })} />
          </div>
          <div style={{ ...styles.label, marginTop: "16px" }}>Generated SQL Preview</div>
          <div style={styles.sqlBox}>{buildSQL(draft)}</div>
          <div style={{ display: "flex", gap: "10px", marginTop: "16px", flexWrap: "wrap" }}>
            <button style={styles.btn(C.success)} onClick={createScheme} disabled={busy}>
              Save To Database
            </button>
            <button style={styles.btn(C.muted, true)} onClick={() => setDraft(null)} disabled={busy}>
              Discard Draft
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function EditPanel({ schemes, onUpdated, pushLog }) {
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save() {
    if (!selected || !form) return;
    setBusy(true);
    setError("");

    try {
      const payload = { ...form, benefit: form.benefit === "" ? null : Number(form.benefit) };
      const data = await api(`/admin/schemes/${selected.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      pushLog(`Scheme ${data.scheme.name} updated.`, C.success);
      onUpdated(data.scheme);
      setSelected(data.scheme);
      setForm(normalizeScheme(data.scheme));
    } catch (err) {
      setError(err.message);
      pushLog(`Update failed: ${err.message}`, C.danger);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div style={{ marginBottom: "12px" }}>
        <span style={styles.chip(C.warn)}>Feature 2</span>
        <span style={{ marginLeft: "10px", fontSize: "13px", fontWeight: "700" }}>Edit Existing Scheme</span>
      </div>

      <div style={styles.card}>
        {schemes.filter((scheme) => scheme.active).map((scheme) => (
          <div key={scheme.id} style={{ ...styles.schemeLine, borderColor: selected?.id === scheme.id ? C.accentHi : C.border }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: "13px", fontWeight: "700" }}>{scheme.name}</div>
              <div style={{ fontSize: "11px", color: C.muted, marginTop: "4px" }}>
                {toINR(scheme.min_income)} to {toINR(scheme.max_income)} | {scheme.occupation} | {scheme.location}
              </div>
            </div>
            <button
              style={styles.btn(C.accent, true)}
              onClick={() => {
                setSelected(scheme);
                setForm(normalizeScheme(scheme));
                setError("");
              }}
            >
              Edit
            </button>
          </div>
        ))}
      </div>

      {form && (
        <div style={styles.card}>
          <div style={{ ...styles.label, color: C.accentHi, marginBottom: "16px" }}>Editing {selected.name}</div>
          {error && <div style={styles.notice(C.danger)}>{error}</div>}
          <div style={{ marginBottom: "14px" }}>
            <label style={styles.label}>Scheme Name</label>
            <input style={styles.input} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div style={{ marginBottom: "14px" }}>
            <label style={styles.label}>Description</label>
            <textarea style={styles.textarea} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div style={styles.row}>
            <div>
              <label style={styles.label}>Min Income</label>
              <input style={styles.input} type="number" value={form.min_income} onChange={(e) => setForm({ ...form, min_income: Number(e.target.value) })} />
            </div>
            <div>
              <label style={styles.label}>Max Income</label>
              <input style={styles.input} type="number" value={form.max_income} onChange={(e) => setForm({ ...form, max_income: Number(e.target.value) })} />
            </div>
          </div>
          <div style={styles.row3}>
            <div>
              <label style={styles.label}>Gender</label>
              <select style={styles.select} value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })}>
                <option>All</option>
                <option>Male</option>
                <option>Female</option>
              </select>
            </div>
            <div>
              <label style={styles.label}>Location</label>
              <input style={styles.input} value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
            </div>
            <div>
              <label style={styles.label}>Occupation</label>
              <input style={styles.input} value={form.occupation} onChange={(e) => setForm({ ...form, occupation: e.target.value })} />
            </div>
          </div>
          <div style={styles.row}>
            <div>
              <label style={styles.label}>Min Age</label>
              <input style={styles.input} type="number" value={form.min_age} onChange={(e) => setForm({ ...form, min_age: Number(e.target.value) })} />
            </div>
            <div>
              <label style={styles.label}>Max Age</label>
              <input style={styles.input} type="number" value={form.max_age} onChange={(e) => setForm({ ...form, max_age: Number(e.target.value) })} />
            </div>
          </div>
          <div style={{ marginBottom: "14px" }}>
            <label style={styles.label}>Benefit Amount</label>
            <input style={styles.input} type="number" value={form.benefit} onChange={(e) => setForm({ ...form, benefit: e.target.value })} />
          </div>
          <div style={{ ...styles.label, marginTop: "16px" }}>Generated SQL Preview</div>
          <div style={styles.sqlBox}>{buildSQL(form, selected.id)}</div>
          <div style={{ display: "flex", gap: "10px", marginTop: "16px", flexWrap: "wrap" }}>
            <button style={styles.btn(C.warn)} onClick={save} disabled={busy}>
              Save Changes
            </button>
            <button style={styles.btn(C.muted, true)} onClick={() => setForm(null)} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function RemovePanel({ schemes, onRemoved, pushLog }) {
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");

  async function deactivate(scheme) {
    setBusyId(scheme.id);
    setError("");

    try {
      const data = await api(`/admin/schemes/${scheme.id}`, { method: "DELETE" });
      pushLog(`Scheme ${data.scheme.name} deactivated.`, C.success);
      onRemoved(data.scheme);
    } catch (err) {
      setError(err.message);
      pushLog(`Deactivation failed: ${err.message}`, C.danger);
    } finally {
      setBusyId(null);
    }
  }

  const active = schemes.filter((scheme) => scheme.active);
  const inactive = schemes.filter((scheme) => !scheme.active);

  return (
    <div>
      <div style={{ marginBottom: "12px" }}>
        <span style={styles.chip(C.danger)}>Feature 3</span>
        <span style={{ marginLeft: "10px", fontSize: "13px", fontWeight: "700" }}>Deactivate Scheme</span>
      </div>

      {error && <div style={styles.notice(C.danger)}>{error}</div>}

      <div style={styles.card}>
        <div style={{ ...styles.notice(C.success), marginBottom: "16px" }}>
          Deactivation is a soft delete. Existing applications and analytics remain intact.
        </div>

        {active.map((scheme) => (
          <div key={scheme.id} style={styles.schemeLine}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: "13px", fontWeight: "700" }}>{scheme.name}</div>
              <div style={{ fontSize: "11px", color: C.muted, marginTop: "4px" }}>
                Benefit {toINR(scheme.benefit)} | {scheme.location}
              </div>
            </div>
            <div style={{ minWidth: "280px" }}>
              <div style={styles.sqlBox}>{buildSQL(scheme, scheme.id, true)}</div>
            </div>
            <button style={styles.btn(C.danger, true)} onClick={() => deactivate(scheme)} disabled={busyId === scheme.id}>
              Deactivate
            </button>
          </div>
        ))}
      </div>

      {inactive.length > 0 && (
        <div style={styles.card}>
          <div style={styles.label}>Inactive Schemes</div>
          {inactive.map((scheme) => (
            <div key={scheme.id} style={{ ...styles.schemeLine, opacity: 0.6 }}>
              <div>
                <div style={{ fontSize: "13px", textDecoration: "line-through" }}>{scheme.name}</div>
                <div style={{ fontSize: "11px", color: C.muted, marginTop: "4px" }}>Preserved in the database history.</div>
              </div>
              <span style={styles.chip(C.muted)}>Inactive</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState(0);
  const [schemes, setSchemes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [logs, pushLog] = useLogs();

  const activeCount = useMemo(() => schemes.filter((scheme) => scheme.active).length, [schemes]);

  async function loadSchemes() {
    setLoading(true);
    setError("");
    try {
      const data = await api("/admin/schemes?include_inactive=true");
      setSchemes(data.schemes || []);
      pushLog(`Loaded ${data.count} schemes from PostgreSQL.`, C.accentHi);
    } catch (err) {
      setError(err.message);
      pushLog(`Load failed: ${err.message}`, C.danger);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSchemes();
  }, []);

  const tabs = ["Upload", "Edit", "Deactivate"];

  return (
    <div style={styles.root}>
      <div style={styles.header}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={styles.badge}>NPIDE</span>
            <h1 style={styles.title}>Policy Engine</h1>
          </div>
          <p style={styles.subtitle}>Connected admin UI for scheme extraction, editing, and deactivation.</p>
        </div>
        <div style={{ marginLeft: "auto", textAlign: "right" }}>
          <div style={{ fontSize: "24px", fontWeight: "700", color: C.accentHi }}>{activeCount}</div>
          <div style={{ fontSize: "10px", color: C.muted, letterSpacing: "1px" }}>Active Schemes</div>
        </div>
      </div>

      <div style={styles.tabs}>
        {tabs.map((label, index) => (
          <button key={label} style={styles.tab(tab === index)} onClick={() => setTab(index)}>
            {label}
          </button>
        ))}
        <button style={{ ...styles.tab(false), marginLeft: "auto" }} onClick={loadSchemes}>
          Refresh
        </button>
      </div>

      <div style={styles.body}>
        {error && <div style={styles.notice(C.danger)}>{error}</div>}
        {loading && <div style={styles.notice(C.warn)}>Loading scheme catalog from the backend.</div>}

        {tab === 0 && <UploadPanel onCreated={loadSchemes} pushLog={pushLog} />}
        {tab === 1 && <EditPanel schemes={schemes} onUpdated={loadSchemes} pushLog={pushLog} />}
        {tab === 2 && <RemovePanel schemes={schemes} onRemoved={loadSchemes} pushLog={pushLog} />}

        <div style={styles.card}>
          <div style={{ ...styles.label, marginBottom: "10px" }}>Backend Activity Log</div>
          <div style={styles.log}>
            {logs.length === 0 && <div>No activity yet.</div>}
            {logs.map((entry, index) => (
              <div key={`${entry.time}-${index}`} style={{ color: entry.color }}>
                <span style={{ color: C.border }}>[{entry.time}]</span> {entry.message}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
