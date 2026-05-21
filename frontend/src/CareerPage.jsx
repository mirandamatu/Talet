import React, { useEffect, useRef, useState } from "react"

const API = "/api"

function apiFetch(path, options = {}) {
  return fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(options.headers || {}),
    },
  }).then(async (res) => {
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      const d = data.detail
      const msg = typeof d === "string" ? d : (d && d.msg) || "Error al procesar la solicitud"
      throw new Error(msg)
    }
    return data
  })
}

function formatDate(iso) {
  if (!iso) return ""
  const d = new Date(iso)
  return d.toLocaleDateString("es-MX", { year: "numeric", month: "long", day: "numeric" })
}

function truncate(text, max = 180) {
  if (!text) return ""
  return text.length > max ? text.slice(0, max) + "…" : text
}

function Tag({ children, color = "cyan" }) {
  const colors = {
    cyan: { bg: "rgba(16,185,129,0.12)", text: "#10b981", border: "rgba(16,185,129,0.25)" },
    green: { bg: "rgba(52,211,153,0.12)", text: "#34d399", border: "rgba(52,211,153,0.25)" },
  }
  const c = colors[color] || colors.cyan
  return (
    <span style={{
      display: "inline-block",
      padding: "3px 12px",
      borderRadius: 999,
      fontSize: "0.857rem",
      fontWeight: 500,
      background: c.bg,
      color: c.text,
      border: `1px solid ${c.border}`,
    }}>
      {children}
    </span>
  )
}

function Spinner() {
  return (
    <div style={{ display: "flex", justifyContent: "center", padding: "64px 0" }}>
      <div style={{
        width: 36, height: 36, borderRadius: "50%",
        border: "3px solid rgba(16,185,129,0.18)",
        borderTopColor: "var(--color-primary, #10b981)",
        animation: "cp-spin 0.7s linear infinite",
      }} />
    </div>
  )
}

function FieldGroup({ label, required, error, hint, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <label style={{ fontSize: "0.929rem", fontWeight: 500, color: "var(--muted, #91a4bf)" }}>
        {label}{required && <span style={{ color: "#fb7185", marginLeft: 3 }}>*</span>}
      </label>
      {children}
      {hint && !error && <span style={{ fontSize: "0.786rem", color: "var(--muted, #91a4bf)" }}>{hint}</span>}
      {error && <span style={{ fontSize: "0.857rem", color: "#fb7185" }}>{error}</span>}
    </div>
  )
}

const inputStyle = {
  width: "100%",
  padding: "10px 14px",
  borderRadius: 12,
  border: "1px solid rgba(164,181,210,0.2)",
  background: "rgba(255,255,255,0.07)",
  color: "var(--text, #eef5ff)",
  fontSize: "0.929rem",
  outline: "none",
  boxSizing: "border-box",
  transition: "border-color 0.15s",
}

function JobList({ client, jobs, onSelect }) {
  return (
    <div>
      <div style={{ marginBottom: 40, textAlign: "center" }}>
        <h1 style={{
          fontSize: "clamp(1.5rem, 5vw, 2rem)",
          fontWeight: 700,
          margin: "0 0 12px",
          background: "linear-gradient(90deg, var(--color-primary, #10b981), #059669)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          lineHeight: 1.2,
        }}>
          {client.name}
        </h1>
        <p style={{ fontSize: "1rem", color: "var(--muted, #91a4bf)", margin: 0 }}>
          {jobs.length === 0
            ? "No hay vacantes abiertas en este momento."
            : `${jobs.length} vacante${jobs.length > 1 ? "s" : ""} abierta${jobs.length > 1 ? "s" : ""}`}
        </p>
      </div>

      {jobs.length === 0 ? (
        <div style={{
          textAlign: "center",
          padding: "40px 20px",
          borderRadius: 18,
          border: "1px dashed rgba(164,181,210,0.2)",
          color: "var(--muted, #91a4bf)",
        }}>
          <div style={{ fontSize: "2rem", marginBottom: 12 }}>🔍</div>
          <p style={{ margin: 0, fontSize: "1rem" }}>Volvé a consultar más adelante.</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {jobs.map((job) => (
            <div
              key={job.id}
              onClick={() => onSelect(job)}
              role="presentation"
              style={{
                background: "rgba(13,25,43,0.88)",
                border: "1px solid rgba(164,181,210,0.15)",
                borderRadius: 18,
                padding: "22px 26px",
                cursor: "pointer",
                transition: "border-color 0.18s, transform 0.15s",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <div style={{ flex: 1 }}>
                  <h2 style={{ fontSize: "1.143rem", fontWeight: 600, margin: "0 0 8px", color: "var(--text, #eef5ff)" }}>
                    {job.title}
                  </h2>
                  <p style={{ fontSize: "0.929rem", color: "var(--muted, #91a4bf)", margin: "0 0 14px", lineHeight: 1.6 }}>
                    {truncate(job.description)}
                  </p>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                    <Tag color="green">Abierta</Tag>
                    <span style={{ fontSize: "0.857rem", color: "var(--muted, #91a4bf)" }}>
                      Publicada el {formatDate(job.created_at)}
                    </span>
                  </div>
                </div>
                <div style={{
                  padding: "8px 18px",
                  borderRadius: 10,
                  background: "linear-gradient(135deg, rgba(16,185,129,0.13), rgba(52,211,153,0.13))",
                  border: "1px solid rgba(16,185,129,0.25)",
                  color: "var(--color-primary, #10b981)",
                  fontSize: "0.929rem",
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                  alignSelf: "center",
                }}>
                  Postularme →
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ApplyForm({ client, job, onBack, onSuccess }) {
  const [form, setForm] = useState({ full_name: "", email: "", personal_description: "" })
  const [cvFile, setCvFile] = useState(null)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const fileRef = useRef()

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
    setErrors((e) => ({ ...e, [field]: "" }))
  }

  function validate() {
    const e = {}
    if (!form.full_name.trim()) e.full_name = "El nombre es obligatorio"
    if (!form.email.trim()) e.email = "El email es obligatorio"
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = "Email inválido"
    if (!cvFile) e.cv = "El CV en PDF es obligatorio"
    else if (!cvFile.name.toLowerCase().endsWith(".pdf")) e.cv = "Solo se aceptan archivos PDF"
    return e
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) { setErrors(errs); return }

    setSubmitting(true)
    try {
      const fd = new FormData()
      fd.append("full_name", form.full_name.trim())
      fd.append("email", form.email.trim().toLowerCase())
      if (form.personal_description.trim()) fd.append("personal_description", form.personal_description.trim())
      fd.append("search_id", String(job.id))
      fd.append("cv", cvFile)

      const result = await apiFetch(`/careers/${client.slug}/apply`, { method: "POST", body: fd })
      onSuccess(result)
    } catch (err) {
      setErrors({ _global: err.message || "Error al enviar la postulación. Intenta nuevamente." })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <button type="button" onClick={onBack} style={{ background: "none", border: "none", color: "var(--muted, #91a4bf)", cursor: "pointer", fontSize: "0.929rem", padding: "0 0 20px" }}>
        ← Volver
      </button>

      <div style={{ background: "rgba(13,25,43,0.88)", border: "1px solid rgba(164,181,210,0.15)", borderRadius: 18, padding: "30px 28px", marginBottom: 24 }}>
        <Tag color="green">Abierta</Tag>
        <h1 style={{ fontSize: "1.286rem", fontWeight: 700, margin: "12px 0 8px", color: "var(--text, #eef5ff)" }}>{job.title}</h1>
        <p style={{ fontSize: "0.929rem", color: "var(--muted, #91a4bf)", margin: 0, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{job.description}</p>
      </div>

      <div style={{ background: "rgba(13,25,43,0.88)", border: "1px solid rgba(164,181,210,0.15)", borderRadius: 18, padding: "30px 28px" }}>
        <h2 style={{ fontSize: "1.143rem", fontWeight: 600, margin: "0 0 24px", color: "var(--text, #eef5ff)" }}>Postulación</h2>
        {errors._global && <div style={{ background: "rgba(255,101,119,0.12)", border: "1px solid rgba(255,101,119,0.3)", borderRadius: 10, padding: "10px 14px", marginBottom: 20, color: "#fb7185" }}>{errors._global}</div>}
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <FieldGroup label="Nombre completo" required error={errors.full_name}>
            <input style={{ ...inputStyle, borderColor: errors.full_name ? "#fb7185" : "rgba(164,181,210,0.2)" }} value={form.full_name} onChange={(e) => set("full_name", e.target.value)} placeholder="Ej. María González" autoComplete="name" />
          </FieldGroup>
          <FieldGroup label="Mail de contacto" required error={errors.email}>
            <input type="email" style={{ ...inputStyle, borderColor: errors.email ? "#fb7185" : "rgba(164,181,210,0.2)" }} value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="tu@email.com" autoComplete="email" />
          </FieldGroup>
          <FieldGroup label="CV (PDF)" required hint="Máx. 10 MB" error={errors.cv}>
            <input ref={fileRef} type="file" accept="application/pdf,.pdf" style={{ ...inputStyle, padding: 8 }} onChange={(e) => { const f = e.target.files?.[0]; if (f) { setCvFile(f); setErrors((err) => ({ ...err, cv: "" })) } }} />
            {cvFile && <small style={{ color: "var(--muted, #91a4bf)" }}>{cvFile.name}</small>}
          </FieldGroup>
          <FieldGroup label="Descripción personal" hint="Opcional">
            <textarea rows={5} style={{ ...inputStyle, resize: "vertical", minHeight: 100, lineHeight: 1.6 }} value={form.personal_description} onChange={(e) => set("personal_description", e.target.value)} placeholder="Contanos brevemente tu experiencia…" />
          </FieldGroup>
          <button type="submit" disabled={submitting} style={{ padding: "13px 28px", borderRadius: 12, border: "none", background: submitting ? "rgba(16,185,129,0.35)" : "linear-gradient(135deg, var(--color-primary, #10b981), #059669)", color: "#042f2e", fontWeight: 700, fontSize: "1rem", cursor: submitting ? "not-allowed" : "pointer", alignSelf: "flex-start" }}>
            {submitting ? "Enviando…" : "Enviar postulación"}
          </button>
        </form>
      </div>
    </div>
  )
}

function SuccessScreen({ jobTitle, serverMessage, onBack }) {
  return (
    <div style={{ textAlign: "center", padding: "60px 20px" }}>
      <h2 style={{ fontSize: "1.429rem", fontWeight: 700, margin: "0 0 10px", color: "#10b981" }}>¡Postulación enviada!</h2>
      <p style={{ fontSize: "1rem", color: "var(--muted, #91a4bf)", maxWidth: 420, margin: "0 auto 28px", lineHeight: 1.6 }}>
        {serverMessage || `Recibimos tu postulación${jobTitle ? ` para ${jobTitle}` : ""}. El equipo revisará tu perfil.`}
      </p>
      <button type="button" onClick={onBack} style={{ padding: "10px 24px", borderRadius: 10, border: "1px solid rgba(164,181,210,0.2)", background: "rgba(255,255,255,0.07)", color: "var(--text, #eef5ff)", fontSize: "0.929rem", cursor: "pointer" }}>
        Volver al inicio
      </button>
    </div>
  )
}

export default function CareerPage({ slug }) {
  const [state, setState] = useState("loading")
  const [data, setData] = useState(null)
  const [selectedJob, setSelectedJob] = useState(null)
  const [successInfo, setSuccessInfo] = useState(null)
  const [errorMsg, setErrorMsg] = useState("")

  useEffect(() => {
    apiFetch(`/careers/${slug}`)
      .then((res) => { setData(res); setState("list") })
      .catch((err) => { setErrorMsg(err.message || "No encontramos esta página."); setState("error") })
  }, [slug])

  useEffect(() => {
    const b = data?.branding
    if (b?.primary_color) document.documentElement.style.setProperty("--color-primary", b.primary_color)
    else document.documentElement.style.removeProperty("--color-primary")
    return () => document.documentElement.style.removeProperty("--color-primary")
  }, [data])

  const logoUrl = data?.branding?.logo_url

  return (
    <div className="career-portal" style={{ minHeight: "100vh", background: "var(--bg, #0a1010)", color: "var(--text, #e8f4ef)" }}>
      <style>{`@keyframes cp-spin { to { transform: rotate(360deg); } }`}</style>
      <header style={{ borderBottom: "1px solid rgba(164,181,210,0.1)", padding: "14px 24px", background: "rgba(13,25,43,0.7)", backdropFilter: "blur(14px)", display: "flex", alignItems: "center", gap: 12 }}>
        {logoUrl ? <img src={logoUrl} alt="" style={{ maxHeight: 32, maxWidth: 140, objectFit: "contain" }} /> : <span style={{ fontSize: "1.143rem", fontWeight: 700, color: "var(--color-primary, #10b981)" }}>aptia</span>}
        <span style={{ fontSize: "0.929rem", color: "var(--muted, #91a4bf)" }}>Portal de empleos</span>
      </header>
      <main style={{ maxWidth: 760, margin: "0 auto", padding: "48px 20px 80px" }}>
        {state === "loading" && <Spinner />}
        {state === "error" && <div style={{ textAlign: "center", padding: "80px 20px" }}><h2>Página no encontrada</h2><p style={{ color: "var(--muted, #91a4bf)" }}>{errorMsg}</p></div>}
        {state === "list" && data && (
          <JobList client={data.client} jobs={data.jobs} onSelect={(job) => { setSelectedJob(job); setState("apply") }} />
        )}
        {state === "apply" && data && selectedJob && (
          <ApplyForm client={data.client} job={selectedJob} onBack={() => setState("list")} onSuccess={(result) => { setSuccessInfo(result); setState("success") }} />
        )}
        {state === "success" && successInfo && (
          <SuccessScreen jobTitle={selectedJob?.title} serverMessage={successInfo.message} onBack={() => { setState("list"); setSuccessInfo(null); setSelectedJob(null) }} />
        )}
      </main>
    </div>
  )
}
