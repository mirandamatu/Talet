import React, { useEffect, useMemo, useRef, useState } from "react"
import DOMPurify from "dompurify"
import { Document, Page, pdfjs } from "react-pdf"
import { apiFetch } from "./shared/api"
import {
  Avatar,
  EmptyState,
  Feedback,
  Field,
  FileInput,
  Icon,
  PasswordInput,
  Skeleton,
  SkeletonList,
  Stepper,
  StrengthMeter,
  passwordStrength,
  useConfirm,
  useToast
} from "./shared/ui.jsx"
import { analyzeCandidatesForSearch, listCandidateAnalyses, listCandidateSearchAnalyses, matchCandidatesForSearch } from "./features/recruiting/analysis"
import { createConversation, listConversations, listMessages, sendMessage, summarizeConversation } from "./features/hub/hub"
import { generateMailDraft, sendMailDraft } from "./features/recruiting/mail"
import { createCandidateNote, deleteCandidateNote, listCandidateNotes, updateCandidateNote } from "./features/recruiting/notes"
import { createInterviewProposal, disconnectGoogleCalendar, getGoogleCalendarStatus } from "./features/recruiting/calendar"
import { connectGoogleWithPopup } from "./features/recruiting/googleConnect"
import { Login } from "./features/auth/Login.jsx"
import { Notifications } from "./features/notifications/Notifications.jsx"
import BrandMark from "./BrandMark.jsx"

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString()

const ROLE_LABELS = {
  SUPERADMIN: "Admin",
  COMERCIAL: "Comercial",
  TALENT: "Talent",
  CLIENTE: "Cliente"
}

const ROLE_NAV = {
  SUPERADMIN: [
    { key: "overview", label: "Inicio" },
    { key: "calendar", label: "Calendario" },
    { key: "admin", label: "Usuarios y clientes" },
    { key: "profile", label: "Perfil" }
  ],
  COMERCIAL: [
    { key: "overview", label: "Inicio" },
    { key: "searches", label: "Búsquedas" },
    { key: "projects", label: "Proyectos / En curso" },
    { key: "create", label: "Crear búsqueda" },
    { key: "talentBank", label: "Banco de talento" },
    { key: "calendar", label: "Calendario" },
    { key: "metrics", label: "Métricas" },
    { key: "hub", label: "Hub" },
    { key: "notifications", label: "Notificaciones" },
    { key: "profile", label: "Perfil" }
  ],
  TALENT: [
    { key: "overview", label: "Inicio" },
    { key: "searches", label: "Búsquedas" },
    { key: "projects", label: "Proyectos / En curso" },
    { key: "candidates", label: "Candidatos" },
    { key: "talentBank", label: "Banco de talento" },
    { key: "calendar", label: "Calendario" },
    { key: "metrics", label: "Métricas" },
    { key: "hub", label: "Hub" },
    { key: "notifications", label: "Notificaciones" },
    { key: "profile", label: "Perfil" }
  ],
  CLIENTE: [
    { key: "overview", label: "Inicio" },
    { key: "searches", label: "Búsquedas" },
    { key: "projects", label: "Proyectos / En curso" },
    { key: "create", label: "Crear búsqueda" },
    { key: "candidates", label: "Candidatos" },
    { key: "calendar", label: "Calendario" },
    { key: "metrics", label: "Métricas" },
    { key: "hub", label: "Hub" },
    { key: "notifications", label: "Notificaciones" },
    { key: "profile", label: "Perfil" }
  ]
}

const STATUS_LABELS = {
  en_revision: "En revisión",
  entrevistado: "Entrevistado",
  aprobado: "Aprobado",
  descartado: "Descartado",
  rechazado: "Rechazado",
  banco_talent: "Banco activo",
  banco_no_activo: "Banco no activo",
  en_banca: "En banca",
  applied: "Postulado"
}

class ErrorBoundary extends React.Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="error-boundary">
          <h2>Ocurrió un error inesperado.</h2>
          <p>Recargá la página para volver a intentar.</p>
          <button type="button" className="primary-action fit" onClick={() => window.location.reload()}>
            Recargar
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

function normalizeUser(user) {
  if (!user) return null
  const clientIds = Array.isArray(user.client_ids)
    ? user.client_ids
    : (user.client_id ? [user.client_id] : [])
  return { ...user, client_ids: clientIds, organization_id: user.organization_id ?? null }
}

/** Normaliza status de Google; oauth_configured solo true si el backend lo confirma. */
function normalizeCalendarConnection(raw) {
  const st = raw || {}
  return {
    connected: Boolean(st.connected),
    google_email: st.google_email || "",
    expires_at: st.expires_at || null,
    gmail_send_enabled: Boolean(st.gmail_send_enabled),
    oauth_configured: st.oauth_configured === true,
    can_send_mail: Boolean(st.can_send_mail),
  }
}

/** Mensaje claro después de POST /mail/send o propuesta que envía correo */
function mailDeliveredUserMessage(payload) {
  if (!payload) return "Mail enviado correctamente."
  const detail = String(payload.mail_delivery_detail || "").trim()
  const via = payload.mail_sent_via
  if (via === "gmail_oauth") return detail || "Mail enviado con tu cuenta Gmail."
  if (via === "smtp_profile") return detail || "Mail enviado con el servidor SMTP de tu perfil."
  if (via === "smtp_server") return detail || "Mail enviado desde el servidor de correo configurado."
  return detail || "Mail enviado correctamente."
}

function App() {
  const [token, setToken] = useState(localStorage.getItem("token") || "")
  const [user, setUser] = useState(() => normalizeUser(readJson("user")))
  const [active, setActive] = useState("overview")
  const [clients, setClients] = useState([])
  const [searches, setSearches] = useState([])
  const [metricsSummary, setMetricsSummary] = useState(null)
  const [candidatesBySearch, setCandidatesBySearch] = useState({})
  const [globalCandidates, setGlobalCandidates] = useState([])
  const [selectedSearch, setSelectedSearch] = useState(null)
  const [selectedCandidate, setSelectedCandidate] = useState(null)
  const [openCandidateWithEdit, setOpenCandidateWithEdit] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [adminUsers, setAdminUsers] = useState([])
  const [adminClients, setAdminClients] = useState([])
  const [searchAnalyses, setSearchAnalyses] = useState({})
  const [candidateSearchAnalyses, setCandidateSearchAnalyses] = useState([])
  const [mailComposer, setMailComposer] = useState(null)
  const [candidateNotes, setCandidateNotes] = useState([])
  const [calendarConnection, setCalendarConnection] = useState(() => normalizeCalendarConnection(null))
  const [candidateCvHtml, setCandidateCvHtml] = useState("")
  const [loading, setLoading] = useState(false)
  const [busyAction, setBusyAction] = useState("")
  const [error, setError] = useState("")
  const [query, setQuery] = useState("")
  const [clientFilter, setClientFilter] = useState("")
  const [theme, setTheme] = useState(localStorage.getItem("theme") || "light")
  const [recorder, setRecorder] = useState({
    active: false,
    interviewId: null,
    roleContext: "internal_interview",
    transcript: "",
    audioUrl: ""
  })
  const mediaRecorderRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const speechRef = useRef(null)
  const [planLimitPayload, setPlanLimitPayload] = useState(null)
  const [googleConnecting, setGoogleConnecting] = useState(false)
  const [interviewAnalysis, setInterviewAnalysis] = useState(null)
  const toast = useToast()

  const role = user?.role
  const nav = ROLE_NAV[role] || []
  const allCandidates = useMemo(
    () => globalCandidates.length ? globalCandidates : Object.values(candidatesBySearch).flat().filter(Boolean),
    [globalCandidates, candidatesBySearch]
  )
  const stats = useMemo(() => buildStats(searches, allCandidates), [searches, allCandidates])
  const filteredSearches = useMemo(() => {
    const q = query.trim().toLowerCase()
    return searches.filter((search) => {
      const byClient = !clientFilter || String(search.client_id) === String(clientFilter)
      const byText = !q || `${search.title} ${stripHtml(search.job_description)}`.toLowerCase().includes(q)
      return byClient && byText
    })
  }, [searches, query, clientFilter])
  const openSearches = useMemo(
    () => filteredSearches.filter((search) => (search.search_state || "abierta") !== "activa"),
    [filteredSearches]
  )
  const projectSearches = useMemo(
    () => filteredSearches.filter((search) => search.search_state === "activa"),
    [filteredSearches]
  )
  const filteredCandidates = useMemo(() => {
    const q = query.trim().toLowerCase()
    return allCandidates.filter((candidate) => {
      const search = searches.find((item) => Number(item.id) === Number(candidate.search_id))
      const byClient = !clientFilter || String(search?.client_id) === String(clientFilter)
      const byText = !q || `${candidate.full_name} ${candidate.short_profile || ""} ${search?.title || ""}`.toLowerCase().includes(q)
      return byClient && byText
    })
  }, [allCandidates, searches, query, clientFilter])

  useEffect(() => {
    if (!token || !role) return
    refreshAll()
  }, [token, role])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem("theme", theme)
  }, [theme])

  useEffect(() => {
    if (!searches.length || !token || !role || role === "SUPERADMIN") return
    loadAllCandidates(searches)
  }, [searches.length, token, role])

  useEffect(() => () => stopRecording({ silent: true }), [])

  useEffect(() => {
    const fn = (e) => setPlanLimitPayload(e.detail)
    window.addEventListener("aptia-plan-limit", fn)
    return () => window.removeEventListener("aptia-plan-limit", fn)
  }, [])

  async function refreshAll() {
    setLoading(true)
    setError("")
    try {
      if (role === "SUPERADMIN") {
        const [users, adminClientRows, calendarStatus] = await Promise.all([
          apiFetch("/admin/users", {}, token),
          apiFetch("/admin/clients", {}, token),
          getGoogleCalendarStatus(token).catch(() => null)
        ])
        setAdminUsers(users || [])
        setAdminClients(adminClientRows || [])
        setClients(adminClientRows || [])
        if (calendarStatus) setCalendarConnection(normalizeCalendarConnection(calendarStatus))
      } else {
        const [clientRows, searchRows, notificationRows, calendarStatus, metricsData] = await Promise.all([
          apiFetch("/my/clients", {}, token).catch(() => []),
          apiFetch(role === "CLIENTE" ? "/my/searches" : "/searches", {}, token),
          apiFetch("/notifications", {}, token).catch(() => []),
          getGoogleCalendarStatus(token).catch(() => normalizeCalendarConnection(null)),
          apiFetch("/metrics/summary", {}, token).catch(() => null)
        ])
        setClients(uniqueById(clientRows || []))
        setSearches(searchRows || [])
        setNotifications(notificationRows || [])
        setCalendarConnection(normalizeCalendarConnection(calendarStatus))
        setMetricsSummary(metricsData)
      }
    } catch (err) {
      setError(err.message || "No se pudo cargar información.")
    } finally {
      setLoading(false)
    }
  }

  async function loadAllCandidates(searchRows = searches) {
    if (role !== "CLIENTE") {
      // TODO: reemplazar este límite provisorio por paginación real en la UI.
      const rows = await apiFetch("/candidates?limit=200", {}, token).catch(() => null)
      if (rows) {
        setGlobalCandidates(rows || [])
      }
    }
    const pairs = await Promise.all(
      (searchRows || []).map(async (search) => {
        const list = await apiFetch(`/searches/${search.id}/candidates`, {}, token).catch(() => [])
        return [search.id, (list || []).map((candidate) => ({ ...candidate, _search: search }))]
      })
    )
    setCandidatesBySearch(Object.fromEntries(pairs))
  }

  async function openSearch(search) {
    setSelectedCandidate(null)
    setSelectedSearch(search)
    if (!candidatesBySearch[search.id]) {
      const list = await apiFetch(`/searches/${search.id}/candidates`, {}, token)
      setCandidatesBySearch((prev) => ({ ...prev, [search.id]: list || [] }))
    }
    const analyses = await listCandidateAnalyses(search.id, token).catch(() => ({ items: [] }))
    setSearchAnalyses((prev) => ({ ...prev, [search.id]: analyses.items || [] }))
  }

  async function openCandidate(candidate, options = {}) {
    const contextSearchId = candidate.search_id || candidate._search?.id
    const detail = await apiFetch(`/candidates/${candidate.id}${contextSearchId ? `?search_id=${contextSearchId}` : ""}`, {}, token)
    setSelectedCandidate({ ...candidate, ...detail })
    setOpenCandidateWithEdit(!!options.edit)
    const [analyses, notes] = await Promise.all([
      listCandidateSearchAnalyses(candidate.id, token).catch(() => ({ items: [] })),
      listCandidateNotes(candidate.id, token).catch(() => [])
    ])
    setCandidateSearchAnalyses(analyses.items || [])
    setCandidateNotes(notes || [])
    if ((detail.cv_file_name || candidate.cv_file_name || "").toLowerCase().endsWith(".docx")) {
      const cv = await getCandidateCvHtml(candidate.id, token).catch(() => null)
      setCandidateCvHtml(cv?.html || "")
    } else {
      setCandidateCvHtml("")
    }
  }

  async function logout() {
    localStorage.removeItem("token")
    localStorage.removeItem("user")
    setToken("")
    setUser(null)
    setActive("overview")
  }

  async function reanalyzeCandidate(candidateId = selectedCandidate?.id) {
    if (!candidateId) return
    setBusyAction("candidate-ai")
    setError("")
    try {
      const result = await apiFetch(`/ai/candidates/${candidateId}/reanalyze`, { method: "POST" }, token)
      const patch = {
        ai_fit_score: result.score,
        ai_fit_recommendation: result.recommendation,
        ai_fit_summary: result.summary,
        ai_fit_reasons: result.reasons || []
      }
      setSelectedCandidate((prev) => prev && Number(prev.id) === Number(candidateId) ? { ...prev, ...patch } : prev)
      setCandidatesBySearch((prev) => patchCandidateMap(prev, candidateId, patch))
      setGlobalCandidates((prev) => patchCandidateList(prev, candidateId, patch))
    } catch (err) {
      setError(err.message || "No se pudo analizar el candidato.")
    } finally {
      setBusyAction("")
    }
  }

  async function reanalyzeSearch(searchId = selectedSearch?.id) {
    if (!searchId) return
    setBusyAction("search-ai")
    setError("")
    try {
      const result = await apiFetch(`/ai/searches/${searchId}/questions/reanalyze`, { method: "POST" }, token)
      const patch = {
        ai_questions: result.questions || [],
        ai_questions_summary: result.summary,
        ai_questions_needs_follow_up: result.needs_follow_up
      }
      setSearches((prev) => prev.map((search) => Number(search.id) === Number(searchId) ? { ...search, ...patch } : search))
      setSelectedSearch((prev) => prev && Number(prev.id) === Number(searchId) ? { ...prev, ...patch } : prev)
    } catch (err) {
      setError(err.message || "No se pudo analizar la búsqueda.")
    } finally {
      setBusyAction("")
    }
  }

  async function matchAllCandidatesForSearch(searchId = selectedSearch?.id) {
    if (!searchId) return
    setBusyAction("search-match-ai")
    setError("")
    try {
      const result = await matchCandidatesForSearch(searchId, token)
      setSearchAnalyses((prev) => ({ ...prev, [searchId]: result.items || [] }))
    } catch (err) {
      setError(err.message || "No se pudo ejecutar el matching IA.")
    } finally {
      setBusyAction("")
    }
  }

  async function analyzeAllCandidatesForSearch(searchId = selectedSearch?.id) {
    if (!searchId) return
    setBusyAction("search-candidates-ai")
    setError("")
    try {
      const result = await analyzeCandidatesForSearch(searchId, token)
      setSearchAnalyses((prev) => ({ ...prev, [searchId]: result.items || [] }))
    } catch (err) {
      setError(err.message || "No se pudo analizar candidatos para la búsqueda.")
    } finally {
      setBusyAction("")
    }
  }

  async function openMailComposer(initial) {
    setBusyAction("mail-draft")
    setError("")
    try {
      const candidateId = Array.isArray(initial.candidate_ids) ? initial.candidate_ids[0] : initial.candidate_id
      const draft = await generateMailDraft({ ...initial, candidate_id: candidateId }, token)
      setMailComposer({
        ...initial,
        candidate_id: candidateId,
        subject: draft.subject || "",
        body: draft.body || "",
        extra_context: initial.extra_context || ""
      })
    } catch (err) {
      setError(err.message || "No se pudo generar el mail.")
    } finally {
      setBusyAction("")
    }
  }

  async function regenerateMailComposer() {
    if (!mailComposer) return
    return openMailComposer(mailComposer)
  }

  async function handleConnectGoogle() {
    if (googleConnecting) return null
    if (calendarConnection?.oauth_configured !== true) {
      toast.warn(
        "Google no disponible",
        "La integración aún no está activa en la plataforma. Contactá al administrador."
      )
      return null
    }
    setGoogleConnecting(true)
    try {
      await connectGoogleWithPopup(token)
      const st = await getGoogleCalendarStatus(token)
      const next = normalizeCalendarConnection(st)
      setCalendarConnection(next)
      if (next.connected && next.gmail_send_enabled) {
        toast.success("Listo: ya podés enviar correos y usar el calendario.")
      } else if (next.connected) {
        toast.success("Google conectado. Si el envío falla, volvé a conectar y aceptá todos los permisos.")
      }
      return next
    } catch (err) {
      toast.error(err.message || "No se pudo conectar con Google.")
      return null
    } finally {
      setGoogleConnecting(false)
    }
  }

  async function sendCurrentMail() {
    if (!mailComposer) return
    setBusyAction("mail-send")
    setError("")
    try {
      const outreach = await sendMailDraft({
        kind: mailComposer.kind,
        candidate_id: mailComposer.candidate_id,
        search_id: mailComposer.search_id || null,
        subject: mailComposer.subject,
        body: mailComposer.body
      }, token)
      toast.success(mailDeliveredUserMessage(outreach))
      setMailComposer(null)
    } catch (err) {
      const msg = err.message || "No se pudo enviar el mail."
      setError(msg)
      toast.error(msg)
    } finally {
      setBusyAction("")
    }
  }

  async function addCandidateNote(payload) {
    if (!selectedCandidate?.id) return
    setBusyAction("note-save")
    try {
      const note = await createCandidateNote(selectedCandidate.id, payload, token)
      setCandidateNotes((prev) => [note, ...prev])
    } finally {
      setBusyAction("")
    }
  }

  async function editCandidateNote(noteId, payload) {
    if (!selectedCandidate?.id) return
    const updated = await updateCandidateNote(selectedCandidate.id, noteId, payload, token)
    setCandidateNotes((prev) => prev.map((item) => Number(item.id) === Number(noteId) ? updated : item))
  }

  async function removeCandidateNote(noteId) {
    if (!selectedCandidate?.id) return
    await deleteCandidateNote(selectedCandidate.id, noteId, token)
    setCandidateNotes((prev) => prev.filter((item) => Number(item.id) !== Number(noteId)))
  }

  async function persistTranscript(interviewId, candidateId, sourceType, content) {
    setBusyAction("transcript-save")
    try {
      return await saveTranscript({ interview_id: interviewId, candidate_id: candidateId, source_type: sourceType, content }, token)
    } finally {
      setBusyAction("")
    }
  }

  async function markNotificationsRead(ids = []) {
    if (!ids.length) {
      await apiFetch("/notifications/read-all", { method: "POST" }, token)
    } else {
      await apiFetch("/notifications/read", { method: "POST", body: JSON.stringify({ ids }) }, token)
    }
    const rows = await apiFetch("/notifications", {}, token).catch(() => [])
    setNotifications(rows || [])
  }

  async function archiveNotifications(ids) {
    if (!ids?.length) return
    await apiFetch("/notifications/archive", { method: "POST", body: JSON.stringify({ ids }) }, token)
    const rows = await apiFetch("/notifications", {}, token).catch(() => [])
    setNotifications(rows || [])
  }

  async function analyzeInterview(interview, roleContext = "internal_interview", transcriptOverride = "") {
    const interviewId = String(interview?.id || "")
    if (!interviewId || interviewId.startsWith("m_")) {
      setError("Para análisis IA la entrevista debe estar registrada en backend.")
      return
    }
    if (!transcriptOverride) {
      setInterviewAnalysis({ interview, roleContext, transcript: "", result: null })
      return
    }
    const transcript = transcriptOverride
    if (!transcript || transcript.trim().length < 40) {
      setError("La transcripción es muy corta para generar una devolución útil.")
      return
    }
    setBusyAction("interview-ai")
    setError("")
    try {
      const result = await apiFetch(`/ai/interviews/${interviewId}/analyze`, {
        method: "POST",
        body: JSON.stringify({ transcript: transcript.trim(), role_context: roleContext })
      }, token)
      setInterviewAnalysis({ interview, roleContext, transcript: transcript.trim(), result })
      toast.success("Análisis generado", "La devolución IA quedó disponible en el panel.")
      const rows = await apiFetch("/notifications", {}, token).catch(() => [])
      setNotifications(rows || [])
    } catch (err) {
      setError(err.message || "No se pudo analizar la entrevista.")
    } finally {
      setBusyAction("")
    }
  }

  async function startRecording(interview, roleContext = "internal_interview") {
    const interviewId = String(interview?.id || "")
    if (!interviewId || interviewId.startsWith("m_")) {
      setError("Para grabar con IA la entrevista debe estar registrada en backend.")
      return
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Tu navegador no soporta grabación desde esta vista.")
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const chunks = []
      let finalTranscript = ""
      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder
      mediaStreamRef.current = stream
      mediaRecorder.ondataavailable = (event) => {
        if (event.data?.size) chunks.push(event.data)
      }
      mediaRecorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop())
        const blob = new Blob(chunks, { type: "audio/webm" })
        const audioUrl = URL.createObjectURL(blob)
        setRecorder((prev) => ({ ...prev, active: false, transcript: prev.transcript || finalTranscript, audioUrl }))
      }
      setRecorder((prev) => {
        if (prev.audioUrl) URL.revokeObjectURL(prev.audioUrl)
        return { active: true, interviewId, roleContext, transcript: "", audioUrl: "" }
      })
      const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
      if (Recognition) {
        const recognition = new Recognition()
        recognition.lang = "es-AR"
        recognition.continuous = true
        recognition.interimResults = true
        recognition.onresult = (event) => {
          let finalText = ""
          let interimText = ""
          for (let i = event.resultIndex; i < event.results.length; i += 1) {
            if (event.results[i].isFinal) finalText += `${event.results[i][0].transcript} `
            else interimText += `${event.results[i][0].transcript} `
          }
          if (finalText.trim()) {
            finalTranscript = `${finalTranscript} ${finalText}`.trim()
          }
          const liveTranscript = `${finalTranscript} ${interimText}`.trim()
          setRecorder((prev) => ({ ...prev, transcript: liveTranscript }))
        }
        recognition.onerror = (event) => {
          setError(`No se pudo sincronizar la transcripción: ${event.error || "error del navegador"}. Podés escribirla manualmente.`)
        }
        recognition.onend = () => {
          if (mediaRecorderRef.current?.state === "recording") {
            try {
              recognition.start()
            } catch (_) {
              // El navegador puede rechazar un reinicio inmediato.
            }
          }
        }
        speechRef.current = recognition
        recognition.start()
      }
      mediaRecorder.start(1000)
    } catch (err) {
      setError(err.message || "No se pudo iniciar la grabación.")
    }
  }

  function stopRecording(options = {}) {
    try {
      speechRef.current?.stop?.()
    } catch (_) {
      // noop
    }
    speechRef.current = null
    if (mediaRecorderRef.current?.state && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop()
    } else if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop())
    }
    mediaRecorderRef.current = null
    mediaStreamRef.current = null
    if (!options.silent) setRecorder((prev) => ({ ...prev, active: false }))
  }

  if (!token || !user) {
    return (
      <Login
        onLogin={(nextToken, nextUser) => {
          const normalized = normalizeUser(nextUser)
          localStorage.setItem("token", nextToken)
          localStorage.setItem("user", JSON.stringify(normalized))
          setToken(nextToken)
          setUser(normalized)
        }}
      />
    )
  }

  return (
    <div className="app-shell">
      <Sidebar
        role={role}
        user={user}
        active={active}
        nav={nav}
        onSelect={(key) => {
          setActive(key)
          setSelectedSearch(null)
          setSelectedCandidate(null)
        }}
        onLogout={logout}
      />
      <main className="workspace">
        <Topbar
          active={active}
          role={role}
          loading={loading}
          query={query}
          setQuery={setQuery}
          clients={clients}
          clientFilter={clientFilter}
          setClientFilter={setClientFilter}
          notificationCount={notifications.filter((item) => item.status === "unread").length}
          refreshAll={refreshAll}
          theme={theme}
          onToggleTheme={() => setTheme((current) => current === "dark" ? "light" : "dark")}
          onOpenNotifications={() => setActive("notifications")}
        />
        {error && <Feedback variant="error" title="Ocurrió un error">{error}</Feedback>}
        {active === "overview" && (
          <Overview role={role} stats={stats} metricsSummary={metricsSummary} searches={searches} candidates={allCandidates} clients={clients} loading={loading} setActive={setActive} />
        )}
        {active === "metrics" && (
          <Metrics role={role} stats={stats} metricsSummary={metricsSummary} searches={searches} candidates={allCandidates} clients={clients} loading={loading} />
        )}
        {active === "searches" && !selectedSearch && (
          <SearchesView searches={openSearches} clients={clients} role={role} token={token} mode="searches" loading={loading} onOpen={openSearch} onRefresh={refreshAll} />
        )}
        {active === "projects" && !selectedSearch && (
          <SearchesView searches={projectSearches} clients={clients} role={role} token={token} mode="projects" loading={loading} onOpen={openSearch} onRefresh={refreshAll} />
        )}
        {(active === "searches" || active === "projects") && selectedSearch && !selectedCandidate && (
          <SearchDetail
            search={selectedSearch}
            role={role}
            token={token}
            candidates={candidatesBySearch[selectedSearch.id] || []}
            allCandidates={globalCandidates}
            analyses={searchAnalyses[selectedSearch.id] || []}
            busyAction={busyAction}
            onBack={() => setSelectedSearch(null)}
            onOpenCandidate={openCandidate}
            onReloadCandidates={() => loadAllCandidates(searches)}
            onReanalyzeSearch={() => reanalyzeSearch(selectedSearch.id)}
            onAnalyzeCandidates={() => analyzeAllCandidatesForSearch(selectedSearch.id)}
            onMatchCandidates={() => matchAllCandidatesForSearch(selectedSearch.id)}
            onComposeMail={openMailComposer}
            onChanged={async () => {
              await refreshAll()
              setSelectedSearch(null)
            }}
          />
        )}
        {active === "candidates" && !selectedCandidate && (
          <CandidatesView
            candidates={filteredCandidates}
            searches={searches}
            clients={clients}
            token={token}
            role={role}
            loading={loading}
            onOpen={openCandidate}
            onChanged={() => loadAllCandidates(searches)}
          />
        )}
        {selectedCandidate && (
          <CandidateDetail
            candidate={selectedCandidate}
            role={role}
            token={token}
            busyAction={busyAction}
            setBusyAction={setBusyAction}
            startInEditMode={openCandidateWithEdit}
            searchAnalyses={candidateSearchAnalyses}
            notes={candidateNotes}
            candidateCvHtml={candidateCvHtml}
            recorder={recorder}
            setRecorder={setRecorder}
            onBack={() => setSelectedCandidate(null)}
            onReanalyze={() => reanalyzeCandidate(selectedCandidate.id)}
            onAnalyzeInterview={analyzeInterview}
            onStartRecording={startRecording}
            onStopRecording={stopRecording}
            onAnalyzeRecording={() => analyzeInterview({ id: recorder.interviewId }, recorder.roleContext, recorder.transcript)}
            onSaveTranscript={persistTranscript}
            onAddNote={addCandidateNote}
            onEditNote={editCandidateNote}
            onDeleteNote={removeCandidateNote}
            onComposeMail={openMailComposer}
            onCandidatePatch={(patch) => {
              setSelectedCandidate((prev) => prev ? { ...prev, ...patch } : prev)
              setCandidatesBySearch((prev) => patchCandidateMap(prev, selectedCandidate.id, patch))
              setGlobalCandidates((prev) => patchCandidateList(prev, selectedCandidate.id, patch))
            }}
          />
        )}
        {active === "create" && (
          <CreateSearch token={token} clients={clients} role={role} onCreated={async () => {
            await refreshAll()
            setActive("searches")
          }} />
        )}
        {active === "notifications" && (
          <Notifications
            items={notifications}
            onReadAll={() => markNotificationsRead()}
            onMarkRead={(id) => markNotificationsRead([id])}
            onArchive={archiveNotifications}
          />
        )}
        {active === "calendar" && (
          <CalendarView token={token} clients={clients} role={role} searches={searches} candidates={allCandidates} />
        )}
        {active === "talentBank" && (
          <TalentBankView token={token} searches={searches} onRefresh={refreshAll} role={role} />
        )}
        {active === "hub" && (
          <HubView token={token} role={role} clients={clients} />
        )}
        {active === "profile" && (
          <ProfileSettings
            token={token}
            user={user}
            calendarConnection={calendarConnection}
            setCalendarConnection={setCalendarConnection}
            onConnectGoogle={handleConnectGoogle}
            googleConnecting={googleConnecting}
          />
        )}
        {active === "admin" && role === "SUPERADMIN" && (
          <AdminPanel users={adminUsers} clients={adminClients} token={token} onRefresh={refreshAll} />
        )}
      </main>
      {mailComposer && (
        <MailComposerModal
          value={mailComposer}
          busy={busyAction === "mail-draft" || busyAction === "mail-send"}
          canSendMail={calendarConnection?.can_send_mail}
          oauthConfigured={calendarConnection?.oauth_configured === true}
          googleConnecting={googleConnecting}
          onConnectGoogle={() => void handleConnectGoogle()}
          onClose={() => setMailComposer(null)}
          onChange={setMailComposer}
          onRegenerate={regenerateMailComposer}
          onSend={sendCurrentMail}
        />
      )}
      {interviewAnalysis && (
        <InterviewAnalysisModal
          value={interviewAnalysis}
          busy={busyAction === "interview-ai"}
          onChange={setInterviewAnalysis}
          onClose={() => setInterviewAnalysis(null)}
          onAnalyze={(transcript) => analyzeInterview(interviewAnalysis.interview, interviewAnalysis.roleContext, transcript)}
        />
      )}
      {planLimitPayload && (
        <div className="modal-backdrop" role="presentation" onClick={() => setPlanLimitPayload(null)}>
          <div className="modal-card panel" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <h3>{planLimitPayload.code === "trial_expired" ? "Prueba finalizada" : "Límite del plan"}</h3>
            <p style={{ color: "var(--muted)", marginTop: 8, lineHeight: 1.5 }}>
              {planLimitPayload.code === "trial_expired"
                ? "Tu período de prueba terminó. Actualizá el plan para seguir creando usuarios, clientes o búsquedas."
                : `Alcanzaste el máximo de ${planLimitPayload.limit_type} para el plan ${planLimitPayload.plan}. Considerá pasar a ${planLimitPayload.upgrade_to}.`}
            </p>
            {planLimitPayload.max != null && planLimitPayload.current != null && (
              <p className="text-sm" style={{ marginTop: 12 }}>
                Uso actual: <strong>{planLimitPayload.current}</strong> / <strong>{planLimitPayload.max}</strong>
              </p>
            )}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
              <button type="button" className="primary-action" onClick={() => setPlanLimitPayload(null)}>Entendido</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function AppWithErrorBoundary() {
  return (
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  )
}

const NAV_ICONS = {
  overview: "info",
  searches: "search",
  create: "plus",
  candidates: "users",
  talentBank: "users",
  calendar: "calendar",
  metrics: "info",
  notifications: "bell",
  admin: "users",
  profile: "users"
}

function Sidebar({ role, user, active, nav, onSelect, onLogout }) {
  const confirm = useConfirm()
  async function handleLogout() {
    const ok = await confirm({
      title: "¿Cerrar sesión?",
      description: "Vas a tener que volver a ingresar tus credenciales.",
      confirmLabel: "Cerrar sesión",
      cancelLabel: "Cancelar",
      variant: "warn"
    })
    if (ok) onLogout()
  }
  return (
    <aside className="sidebar" aria-label="Menú principal">
      <div className="sidebar-brand">
        <BrandMark small />
        <div>
          <strong>Atipia</strong>
          <span>{ROLE_LABELS[role] || "Usuario"}</span>
        </div>
      </div>
      <nav aria-label="Navegación principal">
        {nav.map((item) => (
          <button
            key={item.key}
            type="button"
            className={active === item.key ? "nav-item active" : "nav-item"}
            onClick={() => onSelect(item.key)}
            aria-current={active === item.key ? "page" : undefined}
          >
            <Icon name={NAV_ICONS[item.key] || "info"} size={13} />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-user">
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Avatar name={user.full_name || user.email} size="sm" />
          <div style={{ display: "grid", gap: 2, minWidth: 0 }}>
            <strong>{user.full_name || user.email}</strong>
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{user.email}</span>
          </div>
        </div>
        <small>{ROLE_LABELS[role] || "Usuario"}</small>
      </div>
      <button type="button" className="ghost-action" onClick={handleLogout}>
        <Icon name="logout" size={16} />
        Cerrar sesión
      </button>
    </aside>
  )
}

function Topbar({ active, role, loading, query, setQuery, clients, clientFilter, setClientFilter, notificationCount, refreshAll, theme, onToggleTheme, onOpenNotifications }) {
  const themeIcon = theme === "dark" ? "sun" : "moon"
  const themeLabel = theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">{ROLE_LABELS[role] || "Portal"}</p>
        <h1>{titleFor(active)}</h1>
        <p className="topbar-subtitle">{topbarCopy(active, role)}</p>
      </div>
      <div className="topbar-controls">
        <input
          className="search-input with-icon"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar búsquedas, candidatos o clientes..."
          aria-label="Buscar"
        />
        {clients.length > 1 && (
          <select
            value={clientFilter}
            onChange={(event) => setClientFilter(event.target.value)}
            aria-label="Filtrar por cliente"
          >
            <option value="">Todos los clientes</option>
            {clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
          </select>
        )}
        <button
          type="button"
          className="icon-action"
          onClick={onToggleTheme}
          aria-label={themeLabel}
          title={themeLabel}
        >
          <Icon name={themeIcon} size={18} />
        </button>
        <button
          type="button"
          className="icon-action"
          onClick={refreshAll}
          aria-label={loading ? "Actualizando datos" : "Actualizar datos"}
          title="Actualizar"
          disabled={loading}
          data-busy={loading || undefined}
        >
          <Icon name="refresh" size={18} />
        </button>
        <button
          type="button"
          className="notification-pill icon"
          onClick={onOpenNotifications}
          aria-label={notificationCount > 0 ? `${notificationCount} notificaciones pendientes` : "Sin notificaciones pendientes"}
          title="Notificaciones"
        >
          <Icon name="bell" size={18} />
          {notificationCount > 0 && <span className="count">{notificationCount > 99 ? "99+" : notificationCount}</span>}
        </button>
      </div>
    </header>
  )
}

function Overview({ role, stats, metricsSummary, searches, candidates, clients, loading, setActive }) {
  const recent = candidates.slice(0, 5)
  return (
    <div className="view-stack">
      <section className="hero-card">
        <div>
          <p className="eyebrow">Panel principal</p>
          <h2>{overviewCopy(role).title}</h2>
          <p>{overviewCopy(role).text}</p>
        </div>
        <button type="button" className="primary-action" onClick={() => setActive(role === "SUPERADMIN" ? "admin" : "metrics")}>
          {role === "SUPERADMIN" ? "Administrar" : "Ver métricas"}
          <Icon name="arrowRight" size={14} />
        </button>
      </section>
      <KpiGrid stats={stats} metricsSummary={metricsSummary} loading={loading} />
      {metricsSummary?.sections?.length > 0 && (
        <section className="content-grid two">
          {metricsSummary.sections.map((section) => (
            <Panel key={section.title} title={section.title}>
              <p>{section.description}</p>
            </Panel>
          ))}
        </section>
      )}
      <section className="content-grid two">
        <Panel title="Búsquedas abiertas y activas">
          {searches.length === 0 ? (
            <EmptyState
              icon="search"
              title="No hay búsquedas cargadas"
              description="Empezá creando una nueva búsqueda para ver candidatos y métricas."
              action={<button type="button" className="primary-action" onClick={() => setActive("create")}><Icon name="plus" size={14} />Crear búsqueda</button>}
            />
          ) : (
            <div className="mini-list">
              {searches.slice(0, 6).map((search) => (
                <div key={search.id} className="mini-row">
                  <span>{search.title}</span>
                  <small>{clientName(clients, search.client_id)} · {searchStateLabel(search.search_state)}</small>
                </div>
              ))}
            </div>
          )}
        </Panel>
        <Panel title="Últimos candidatos">
          {recent.length === 0 ? (
            <EmptyState
              icon="users"
              title="Sin candidatos todavía"
              description="Cuando subas candidatos vas a verlos acá ordenados por fecha."
            />
          ) : (
            <div className="mini-list">
              {recent.map((candidate) => (
                <div key={candidate.id} className="mini-row">
                  <span>{candidate.full_name}</span>
                  <CandidateAiBadge candidate={candidate} />
                </div>
              ))}
            </div>
          )}
        </Panel>
      </section>
    </div>
  )
}

function KpiGrid({ stats, metricsSummary, loading = false }) {
  const searchSummary = metricsSummary?.searches
  if (loading) {
    return (
      <section className="kpi-grid" aria-busy="true">
        {Array.from({ length: 5 }).map((_, idx) => (
          <article className="kpi-card" key={idx}>
            <Skeleton width="60%" />
            <Skeleton width={64} height={28} />
          </article>
        ))}
      </section>
    )
  }
  return (
    <section className="kpi-grid">
      <Kpi label="Búsquedas abiertas" value={searchSummary?.abiertas ?? stats.searches} tone="blue" />
      <Kpi label="Búsquedas activas" value={searchSummary?.activas ?? 0} tone="green" />
      <Kpi label="Búsquedas eliminadas" value={searchSummary?.eliminadas ?? 0} tone="red" />
      <Kpi label="Candidatos" value={stats.candidates} tone="green" />
      <Kpi label="Match IA promedio" value={`${stats.averageAi}%`} tone="amber" />
    </section>
  )
}

function Kpi({ label, value, tone }) {
  return (
    <article className={`kpi-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

function Metrics({ role, stats, metricsSummary, searches, candidates, clients, loading = false }) {
  const statusSegments = [
    { key: "en_revision", label: "En revisión", value: stats.byStatus.en_revision, color: "#f8c14a" },
    { key: "entrevistado", label: "Entrevistado", value: stats.byStatus.entrevistado, color: "#34d399" },
    { key: "aprobado", label: "Aprobado", value: stats.byStatus.aprobado, color: "#10b981" },
    { key: "descartado", label: "Descartado", value: stats.byStatus.descartado, color: "#ff6577" }
  ]
  const aiBars = candidates
    .filter((candidate) => Number.isFinite(Number(candidate.ai_fit_score)))
    .sort((a, b) => Number(b.ai_fit_score) - Number(a.ai_fit_score))
    .slice(0, 8)
    .map((candidate) => ({ key: candidate.id, label: candidate.full_name, value: Math.round(Number(candidate.ai_fit_score)), color: candidate.ai_fit_recommendation ? "#10b981" : "#fb7185" }))
  const clientBars = groupSearchesByClient(searches).map((item) => ({ key: item.client_id, label: clientName(clients, item.client_id), value: item.count, color: "#34d399" }))
  const searchTypeBars = [
    { key: "abiertas", label: "Abiertas", value: metricsSummary?.searches?.abiertas || 0, color: "#10b981" },
    { key: "activas", label: "Activas", value: metricsSummary?.searches?.activas || 0, color: "#34d399" },
    { key: "eliminadas", label: "Eliminadas", value: metricsSummary?.searches?.eliminadas || 0, color: "#ff6577" }
  ]

  return (
    <div className="view-stack">
      <KpiGrid stats={stats} metricsSummary={metricsSummary} loading={loading} />
      <section className="content-grid two">
        <Panel title={role === "COMERCIAL" ? "Embudo de búsquedas" : "Estado de candidatos"}>
          <DonutChart segments={statusSegments} centerValue={stats.candidates} centerLabel="Candidatos" />
        </Panel>
        <Panel title="Tipos de búsquedas">
          <BarChart items={searchTypeBars} empty="No hay búsquedas para mostrar." />
        </Panel>
      </section>
      <section className="content-grid two">
        <Panel title="Ranking IA de candidatos">
          <BarChart items={aiBars} max={100} suffix="%" empty="Aún no hay scores IA." />
        </Panel>
        <Panel title="Resumen operativo">
          <div className="mini-list">
            <div className="mini-row"><span>Rol actual</span><small>{ROLE_LABELS[metricsSummary?.role || role] || role}</small></div>
            <div className="mini-row"><span>Clientes visibles</span><small>{metricsSummary?.scope?.clients_total ?? clients.length}</small></div>
            {role === "SUPERADMIN" && (
              <>
                <div className="mini-row"><span>Talents</span><small>{metricsSummary?.scope?.talent_total ?? 0}</small></div>
                <div className="mini-row"><span>Comerciales</span><small>{metricsSummary?.scope?.commercial_total ?? 0}</small></div>
                <div className="mini-row"><span>Clientes usuario</span><small>{metricsSummary?.scope?.client_user_total ?? 0}</small></div>
              </>
            )}
          </div>
        </Panel>
      </section>
      <Panel title="Clientes con más búsquedas">
        <BarChart items={clientBars} empty="No hay búsquedas por cliente." />
      </Panel>
    </div>
  )
}

function SearchesView({ searches, clients, role, token, mode = "searches", loading = false, onOpen, onRefresh }) {
  const grouped = {
    abierta: searches.filter((search) => (search.search_state || "abierta") === "abierta"),
    activa: searches.filter((search) => search.search_state === "activa"),
    desactivada: searches.filter((search) => search.search_state === "desactivada"),
    eliminada: searches.filter((search) => search.search_state === "eliminada")
  }
  async function moveSearch(search, manualState) {
    await apiFetch(`/searches/${search.id}`, {
      method: "PATCH",
      body: JSON.stringify({ manual_state: manualState })
    }, token)
    await onRefresh?.()
  }
  return (
    <div className="view-stack">
      {(mode === "projects"
        ? [{ key: "activa", title: "Proyectos / En curso" }]
        : [
          { key: "abierta", title: "Búsquedas abiertas" },
          { key: "desactivada", title: "Búsquedas desactivadas" },
          { key: "eliminada", title: "Búsquedas eliminadas" }
        ]
      ).map((group) => (
        <Panel key={group.key} title={`${group.title} (${grouped[group.key].length})`}>
          {loading ? (
            <SkeletonList rows={3} />
          ) : (
          <section className="card-grid">
            {grouped[group.key].map((search) => (
              <article key={search.id} className="search-card">
                <div className="card-topline">
                  <span>{clientName(clients, search.client_id)}</span>
                  <span className={`badge ${search.search_state === "activa" ? "ok" : search.search_state === "eliminada" ? "danger" : ""}`}>
                    {searchStateLabel(search.search_state)}
                  </span>
                </div>
                <h3>{search.title}</h3>
                <p>{truncate(stripHtml(search.job_description), 180)}</p>
                <div className="mini-list">
                  <div className="mini-row"><span>Candidatos</span><small>{search.candidate_count || 0}</small></div>
                  <div className="mini-row"><span>Con cliente / activos</span><small>{search.active_candidate_count || 0}</small></div>
                </div>
                <div className="card-actions">
                  <button type="button" className="primary-action small" onClick={() => onOpen(search)}>
                    Abrir búsqueda
                    <Icon name="arrowRight" size={12} />
                  </button>
                  {(role === "CLIENTE" || role === "COMERCIAL" || role === "SUPERADMIN") && (
                    <>
                      {group.key !== "abierta" && <button type="button" className="ghost-action small" onClick={() => moveSearch(search, "abierta")}>Mover a abierta</button>}
                      {group.key !== "activa" && <button type="button" className="ghost-action small" onClick={() => moveSearch(search, "activa")}>Mover a activa</button>}
                      {group.key !== "desactivada" && <button type="button" className="ghost-action small" onClick={() => moveSearch(search, "desactivada")}>Desactivar</button>}
                      {group.key !== "eliminada" && <button type="button" className="danger-action small" onClick={() => moveSearch(search, "eliminada")}>Mover a eliminada</button>}
                    </>
                  )}
                </div>
              </article>
            ))}
            {grouped[group.key].length === 0 && (
              <EmptyState icon="search" title={`Sin ${group.title.toLowerCase()}`} description="Cuando muevas búsquedas a este estado las vas a ver acá." />
            )}
          </section>
          )}
        </Panel>
      ))}
    </div>
  )
}

function SearchDetail({ search, role, token, candidates, allCandidates = [], analyses, busyAction, onBack, onOpenCandidate, onReloadCandidates, onReanalyzeSearch, onAnalyzeCandidates, onMatchCandidates, onComposeMail, onChanged }) {
  const toast = useToast()
  const confirm = useConfirm()
  const [metaEditing, setMetaEditing] = useState(false)
  const [jdEditing, setJdEditing] = useState(false)
  const [draft, setDraft] = useState({ title: search.title, job_description: stripHtml(search.job_description), contact_name: search.contact_name || "", contact_email: search.contact_email || "", manual_state: search.manual_state || search.search_state || "abierta" })
  const [meetingFile, setMeetingFile] = useState(null)
  const [meetingFileError, setMeetingFileError] = useState("")
  const [metaErrors, setMetaErrors] = useState({})
  const [message, setMessage] = useState("")
  const [selectedAnalysisIds, setSelectedAnalysisIds] = useState([])

  useEffect(() => {
    setDraft({
      title: search.title,
      job_description: stripHtml(search.job_description),
      contact_name: search.contact_name || "",
      contact_email: search.contact_email || "",
      manual_state: search.manual_state || search.search_state || "abierta"
    })
    setMetaEditing(false)
    setJdEditing(false)
    setMetaErrors({})
  }, [search.id])

  function validateMeta(nextDraft = draft) {
    const errors = {}
    if (!nextDraft.title.trim()) errors.title = "El título es obligatorio."
    if (nextDraft.contact_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(nextDraft.contact_email)) {
      errors.contact_email = "Formato de email inválido."
    }
    setMetaErrors(errors)
    return Object.keys(errors).length === 0
  }

  async function saveMeta() {
    if (!validateMeta()) return
    try {
      const updated = await apiFetch(`/searches/${search.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: draft.title,
          contact_name: draft.contact_name || null,
          contact_email: draft.contact_email || null,
          manual_state: draft.manual_state || null
        })
      }, token)
      setMetaEditing(false)
      setMessage("Datos guardados.")
      onChanged?.(updated)
    } catch (err) {
      toast.error("No se pudo guardar", err.message || "Error.")
    }
  }

  async function saveJdOnly() {
    try {
      const updated = await apiFetch(`/searches/${search.id}`, {
        method: "PATCH",
        body: JSON.stringify({ job_description: draft.job_description })
      }, token)
      setJdEditing(false)
      setMessage("Job description actualizado.")
      onChanged?.(updated)
    } catch (err) {
      toast.error("No se guardó la Job Description", err.message || "Error.")
    }
  }

  async function archiveSearch() {
    const ok = await confirm({
      title: `¿Archivar "${search.title}"?`,
      description: "La búsqueda se ocultará de los listados activos pero se conserva el historial.",
      confirmLabel: "Archivar",
      cancelLabel: "Cancelar",
      variant: "warn"
    })
    if (!ok) return
    try {
      await apiFetch(`/searches/${search.id}`, { method: "DELETE" }, token)
      toast.success("Búsqueda archivada", search.title)
      onChanged?.()
    } catch (err) {
      toast.error("No se pudo archivar", err.message || "Error.")
    }
  }

  async function uploadMeeting() {
    if (!meetingFile) return
    if (meetingFileError) return
    const form = new FormData()
    form.append("file", meetingFile)
    try {
      await apiFetch(`/searches/${search.id}/meeting-upload`, { method: "POST", body: form }, token)
      setMeetingFile(null)
      setMessage("Reunión adjuntada.")
    } catch (err) {
      toast.error("No se pudo subir la reunión", err.message || "Error.")
    }
  }

  function handleMeetingFile(file) {
    setMeetingFileError("")
    if (!file) {
      setMeetingFile(null)
      return
    }
    const allowedExtensions = /\.(pdf|docx)$/i
    const isAllowed = file.type.startsWith("audio/") || file.type.startsWith("video/") || allowedExtensions.test(file.name)
    if (!isAllowed) {
      setMeetingFile(null)
      setMeetingFileError("Usá audio, video, PDF o DOCX.")
      return
    }
    if (file.size > 50 * 1024 * 1024) {
      setMeetingFile(null)
      setMeetingFileError("El archivo no puede superar 50 MB.")
      return
    }
    setMeetingFile(file)
  }

  return (
    <div className="view-stack">
      <button type="button" className="ghost-action fit" onClick={onBack}>Volver</button>
      <div className="search-detail-layout">
        <div className="search-detail-main">
          <section className="detail-hero">
            <div>
              <p className="eyebrow">Búsqueda</p>
              {!metaEditing ? (
                <>
                  <h2>{search.title}</h2>
                  {(search.contact_name || search.contact_email) ? (
                    <p className="muted">
                      {[search.contact_name, search.contact_email].filter(Boolean).join(" · ")}
                    </p>
                  ) : null}
                  <span className="badge">{searchStateLabel(search.search_state)}</span>
                </>
              ) : (
                <div className="form-grid">
                  <Field label="Título" required error={metaErrors.title}>
                    <input
                      value={draft.title}
                      onChange={(event) => {
                        const next = { ...draft, title: event.target.value }
                        setDraft(next)
                        if (metaErrors.title) validateMeta(next)
                      }}
                      onBlur={() => validateMeta()}
                      placeholder="Título"
                    />
                  </Field>
                  <Field label="Contacto">
                    <input value={draft.contact_name} onChange={(event) => setDraft({ ...draft, contact_name: event.target.value })} placeholder="Contacto" />
                  </Field>
                  <Field label="Email contacto" error={metaErrors.contact_email}>
                    <input
                      value={draft.contact_email}
                      onChange={(event) => {
                        const next = { ...draft, contact_email: event.target.value }
                        setDraft(next)
                        if (metaErrors.contact_email) validateMeta(next)
                      }}
                      onBlur={() => validateMeta()}
                      placeholder="Email contacto"
                    />
                  </Field>
                  <Field label="Estado">
                    <select value={draft.manual_state} onChange={(event) => setDraft({ ...draft, manual_state: event.target.value })}>
                      <option value="abierta">Abierta</option>
                      <option value="activa">Activa</option>
                      <option value="desactivada">Desactivada</option>
                      <option value="eliminada">Eliminada</option>
                    </select>
                  </Field>
                </div>
              )}
            </div>
          </section>
          <div className="search-toolbar pill-row">
            {(role === "CLIENTE" || role === "COMERCIAL" || role === "SUPERADMIN") && (
              <>
                {metaEditing
                  ? (
                    <>
                      <button type="button" className="primary-action fit" onClick={saveMeta}>Guardar datos</button>
                      <button type="button" className="ghost-action" onClick={() => setMetaEditing(false)}>Cancelar edición</button>
                    </>
                  )
                  : <button type="button" className="ghost-action fit" onClick={() => setMetaEditing(true)}>Editar datos de búsqueda</button>}
                <button type="button" className="danger-action" onClick={archiveSearch}>Eliminar</button>
              </>
            )}
            {role === "TALENT" && (
              <>
                <button type="button" className="primary-action fit" onClick={onAnalyzeCandidates} disabled={busyAction === "search-candidates-ai"}>
                  {busyAction === "search-candidates-ai" ? "Analizando..." : "Analizar candidatos con IA"}
                </button>
                <button type="button" className="ghost-action fit" onClick={onMatchCandidates} disabled={busyAction === "search-match-ai"}>
                  {busyAction === "search-match-ai" ? "Analizando..." : "Matching IA global"}
                </button>
                {selectedAnalysisIds.length > 0 && (
                  <button
                    type="button"
                    className="ghost-action fit"
                    onClick={() => onComposeMail({
                      kind: "contact",
                      candidate_ids: selectedAnalysisIds,
                      candidate_id: selectedAnalysisIds[0],
                      search_id: search.id
                    })}
                  >
                    Mail a seleccionados
                  </button>
                )}
              </>
            )}
            {role === "COMERCIAL" && (
              <>
                <Field label="Reunión cliente" error={meetingFileError}>
                  <FileInput
                    value={meetingFile}
                    onChange={handleMeetingFile}
                    accept="audio/*,video/*,.pdf,.docx"
                    label="Elegir reunión"
                    hint="Audio, video, PDF o DOCX. Máx. 50 MB."
                  />
                </Field>
                <button type="button" className="ghost-action fit" onClick={uploadMeeting} disabled={!meetingFile}>Subir reunión cliente</button>
              </>
            )}
          </div>
          {message && <Feedback variant="success">{message}</Feedback>}
          <AiQuestionsPanel search={search} busy={busyAction === "search-ai"} onReanalyze={onReanalyzeSearch} />
          {role === "TALENT" && (
            <Panel title="Agente de análisis de candidatos">
              <div className="entity-list">
                {(analyses || []).map((item) => (
                  <article key={`${item.search_id}-${item.candidate_id}`} className="entity-row selectable-row">
                    <label className="check-line compact-check">
                      <input
                        type="checkbox"
                        checked={selectedAnalysisIds.includes(item.candidate_id)}
                        onChange={(event) => setSelectedAnalysisIds((prev) => event.target.checked
                          ? [...new Set([...prev, item.candidate_id])]
                          : prev.filter((id) => Number(id) !== Number(item.candidate_id))
                        )}
                      />
                      <span />
                    </label>
                    <div>
                      <strong>{item.candidate_name}</strong>
                      <span>{formatMatchPercent(item)} · {capitalize(item.recommendation_level || "bajo")}</span>
                      <small className="muted">{item.summary || "Sin resumen generado."}</small>
                    </div>
                    <div className="row-actions">
                      <button
                        type="button"
                        className="ghost-action"
                        onClick={() => onComposeMail({ kind: "contact", candidate_id: item.candidate_id, search_id: search.id })}
                      >
                        Contactar
                      </button>
                    </div>
                  </article>
                ))}
                {(!analyses || analyses.length === 0) && <Empty text="Todavía no se ejecutó el análisis global de candidatos." />}
              </div>
            </Panel>
          )}
          <Panel title="Documentos de la búsqueda">
            <div className="entity-list">
              {(search.documents || []).map((doc) => (
                <article className="entity-row" key={doc.id}>
                  <div>
                    <strong>{doc.file_name}</strong>
                    <span>{doc.kind}</span>
                  </div>
                  <a className="ghost-action" href={doc.file_url} target="_blank" rel="noreferrer">Abrir</a>
                </article>
              ))}
              {(!search.documents || search.documents.length === 0) && <Empty text="No hay documentos adjuntos." />}
            </div>
          </Panel>
          {(role === "TALENT" || role === "SUPERADMIN") && <BankRecommendations token={token} search={search} />}
          {(role === "TALENT" || role === "SUPERADMIN") && (
            <AssignExistingCandidates search={search} candidates={allCandidates} assignedCandidates={candidates} token={token} onAssigned={onReloadCandidates} />
          )}
          <Panel title="Candidatos">
            <div className="entity-list">
              {candidates.map((candidate) => (
                <CandidateRow
                  key={candidate.id}
                  candidate={candidate}
                  token={token}
                  role={role}
                  onOpen={(c, opts) => onOpenCandidate(c, opts)}
                  onChanged={onReloadCandidates}
                />
              ))}
              {candidates.length === 0 && <Empty text="No hay candidatos cargados." />}
            </div>
          </Panel>
        </div>
        <aside className="jd-card">
          <div className="jd-card-head">
            <h4>Job description</h4>
            {(role === "CLIENTE" || role === "COMERCIAL" || role === "SUPERADMIN") && (
              jdEditing ? (
                <div className="pill-row jd-card-actions">
                  <button type="button" className="ghost-action small fit" onClick={() => {
                    setJdEditing(false)
                    setDraft((d) => ({ ...d, job_description: stripHtml(search.job_description) }))
                  }}
                  >
                    Cancelar
                  </button>
                  <button type="button" className="primary-action small fit" onClick={saveJdOnly}>Guardar</button>
                </div>
              ) : (
                <button type="button" className="icon-action mini" onClick={() => setJdEditing(true)} aria-label="Editar Job Description" title="Editar Job Description">
                  <Icon name="edit" size={18} />
                </button>
              )
            )}
          </div>
          {!jdEditing ? (
            <div className="jd-html" dangerouslySetInnerHTML={{ __html: safeDescriptionHtml(search.job_description) }} />
          ) : (
            <textarea className="jd-html jd-textarea" rows={26} value={draft.job_description} onChange={(event) => setDraft({ ...draft, job_description: event.target.value })} aria-label="Editar Job Description" />
          )}
        </aside>
      </div>
    </div>
  )
}

function AssignExistingCandidates({ search, candidates, assignedCandidates, token, onAssigned }) {
  const toast = useToast()
  const [selectedIds, setSelectedIds] = useState([])
  const [busy, setBusy] = useState(false)
  const assignedIds = new Set((assignedCandidates || []).map((candidate) => Number(candidate.id)))
  const available = (candidates || []).filter((candidate) => !assignedIds.has(Number(candidate.id)) && !["aprobado", "activo", "contratado", "en_proyecto", "trabajando"].includes(candidate.assignment_status || candidate.status))

  async function submit(event) {
    event.preventDefault()
    if (!selectedIds.length) return
    setBusy(true)
    try {
      await Promise.all(selectedIds.map((candidateId) => apiFetch(`/candidates/${candidateId}/assignments`, {
        method: "POST",
        body: JSON.stringify({ search_ids: [search.id], status: "en_revision" })
      }, token)))
      toast.success("Candidatos asignados", `${selectedIds.length} candidato(s) agregados a ${search.title}.`)
      setSelectedIds([])
      await onAssigned?.()
    } catch (err) {
      toast.error("No se pudo asignar", err.message || "Error del servidor.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel title="Asignar candidatos existentes" subtitle="Los candidatos se crean desde Candidatos y desde acá solo se vinculan a esta búsqueda.">
      <form className="form-grid" onSubmit={submit}>
        <Field label="Candidatos disponibles">
          <select
            multiple
            size={Math.min(8, Math.max(3, available.length || 3))}
            value={selectedIds.map(String)}
            onChange={(event) => setSelectedIds(Array.from(event.target.selectedOptions).map((option) => Number(option.value)))}
          >
            {available.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {candidate.full_name} {candidate.email ? `· ${candidate.email}` : ""}
              </option>
            ))}
          </select>
        </Field>
        <button type="submit" className="primary-action fit" disabled={busy || !selectedIds.length}>
          {busy ? "Asignando..." : "Asignar a búsqueda"}
        </button>
        {!available.length && <Empty text="No hay candidatos disponibles para asignar." />}
      </form>
    </Panel>
  )
}

function CandidatesView({ candidates, searches, clients, token, role, loading = false, onOpen, onChanged }) {
  return (
    <div className="view-stack">
      {(role === "TALENT" || role === "SUPERADMIN") && (
        <UploadCandidate clients={clients} searches={searches} token={token} onUploaded={onChanged} />
      )}
      <Panel title="Base de candidatos" subtitle="Creá candidatos una vez y asignales una o varias búsquedas.">
        {loading ? (
          <SkeletonList rows={5} />
        ) : (
        <section className="entity-list">
          {candidates.map((candidate) => {
            const search = searches.find((item) => Number(item.id) === Number(candidate.search_id))
            return (
              <CandidateRow
                key={candidate.id}
                candidate={{ ...candidate, _search: search || candidate._search }}
                token={token}
                role={role}
                onOpen={(c, opts) => onOpen(c, opts)}
                onChanged={onChanged}
              />
            )
          })}
          {candidates.length === 0 && <Empty text="No hay candidatos para los filtros actuales." />}
        </section>
        )}
      </Panel>
    </div>
  )
}

function CandidateRow({ candidate, token, role, onOpen, onChanged }) {
  const toast = useToast()
  const confirm = useConfirm()
  const [menuOpen, setMenuOpen] = useState(false)
  const [rowBusy, setRowBusy] = useState("")

  async function sendToBank() {
    const ok = await confirm({
      title: `Enviar a ${candidate.full_name} al banco`,
      description: "Quedará disponible en el banco de talento para futuras búsquedas.",
      confirmLabel: "Enviar al banco",
      cancelLabel: "Cancelar",
      variant: "info"
    })
    if (!ok) return
    setRowBusy("bank")
    try {
      await apiFetch(`/candidates/${candidate.id}/send-to-bank`, { method: "POST" }, token)
      setMenuOpen(false)
      toast.success("Enviado al banco de talento", candidate.full_name)
      onChanged?.()
    } finally {
      setRowBusy("")
    }
  }

  async function deleteCandidate() {
    const ok = await confirm({
      title: `Eliminar a ${candidate.full_name}`,
      description: "Esta acción es permanente y no se puede deshacer.",
      confirmLabel: "Eliminar candidato",
      cancelLabel: "Cancelar",
      variant: "danger"
    })
    if (!ok) return
    setRowBusy("delete")
    try {
      await apiFetch(`/candidates/${candidate.id}`, { method: "DELETE" }, token)
      setMenuOpen(false)
      toast.success("Candidato eliminado", candidate.full_name)
      onChanged?.()
    } finally {
      setRowBusy("")
    }
  }

  const canManage = role === "TALENT" || role === "SUPERADMIN"
  const profileSnippet = stripHtml(candidate.short_profile || "").replace(/\s+/g, " ").trim()
  const assignmentLabel = (candidate.assignments || []).length
    ? (candidate.assignments || []).map((item) => item.search_title || `Búsqueda ${item.search_id}`).slice(0, 2).join(" · ")
    : (candidate._search?.title || (candidate.search_id ? `Búsqueda ${candidate.search_id}` : "Sin búsqueda asignada"))

  return (
    <article className={menuOpen ? "entity-row candidate-list-row menu-open" : "entity-row candidate-list-row"}>
      <div className="candidate-row-meta">
        <div className="candidate-row-name">{candidate.full_name}</div>
        <div className="candidate-row-context">{assignmentLabel}</div>
        {profileSnippet
          ? <div className="candidate-row-profile" title={profileSnippet}>{profileSnippet}</div>
          : <div className="candidate-row-context">Sin descripción cargada.</div>}
      </div>
      <div className="row-actions">
        <StatusBadge status={candidate.status} />
        <CandidateAiBadge candidate={candidate} />
        <button type="button" className="ghost-action small" onClick={() => onOpen(candidate)}>Ver detalle</button>
        {canManage && (
          <button type="button" className="icon-action mini" onClick={() => onOpen(candidate, { edit: true })} aria-label="Editar candidato" title="Editar candidato">
            <Icon name="edit" size={14} />
          </button>
        )}
        {canManage && (
          <div className="row-menu-wrap">
            <button type="button" className="icon-action mini" onClick={() => setMenuOpen((value) => !value)} aria-label="Más acciones del candidato" title="Más acciones">⋯</button>
            {menuOpen && (
              <div className="row-menu">
                {candidate.search_id !== null && candidate.search_id !== undefined && (
                  <button type="button" onClick={sendToBank}>{rowBusy === "bank" ? "Enviando..." : "Enviar a banca"}</button>
                )}
                <button type="button" onClick={deleteCandidate}>{rowBusy === "delete" ? "Eliminando..." : "Eliminar candidato"}</button>
              </div>
            )}
          </div>
        )}
      </div>
    </article>
  )
}

function CandidateDetail({ candidate, role, token, busyAction, setBusyAction, startInEditMode, searchAnalyses, notes, candidateCvHtml, recorder, setRecorder, onBack, onReanalyze, onAnalyzeInterview, onStartRecording, onStopRecording, onAnalyzeRecording, onSaveTranscript, onAddNote, onEditNote, onDeleteNote, onComposeMail, onCandidatePatch }) {
  const toast = useToast()
  const confirm = useConfirm()
  const [interviews, setInterviews] = useState([])
  const [selectedInterview, setSelectedInterview] = useState(null)
  const [editingCandidate, setEditingCandidate] = useState(false)
  const [candidateDraft, setCandidateDraft] = useState({
    full_name: candidate.full_name || "",
    email: candidate.email || "",
    short_profile: candidate.short_profile || ""
  })
  const [status, setStatus] = useState(candidate.status || "en_revision")
  const [feedback, setFeedback] = useState({ main_reason: "otros", comment: "" })
  const [newNote, setNewNote] = useState("")
  const [visibleRoles, setVisibleRoles] = useState(["TALENT", "COMERCIAL"])
  const [visibleUserIds, setVisibleUserIds] = useState([])
  const [users, setUsers] = useState([])
  const [uploadedTranscript, setUploadedTranscript] = useState(null)

  useEffect(() => {
    apiFetch(`/candidates/${candidate.id}/interviews`, {}, token).then(setInterviews).catch(() => setInterviews([]))
    apiFetch("/calendar/invite-users", {}, token).then(setUsers).catch(() => setUsers([]))
  }, [candidate.id, token])

  useEffect(() => {
    setCandidateDraft({
      full_name: candidate.full_name || "",
      email: candidate.email || "",
      short_profile: candidate.short_profile || ""
    })
  }, [candidate.id, candidate.full_name, candidate.email, candidate.short_profile])

  useEffect(() => {
    if (!startInEditMode || !(role === "TALENT" || role === "SUPERADMIN")) return
    setEditingCandidate(true)
  }, [candidate.id, startInEditMode, role])

  async function saveStatus() {
    setBusyAction("candidate-status")
    const effectiveStatus = status === "descartado" ? "rechazado" : status
    const body = effectiveStatus === "rechazado"
      ? { status: effectiveStatus, feedback: { main_reason: feedback.main_reason, comment: feedback.comment, ratings_json: {} } }
      : { status: effectiveStatus, feedback: { comment: feedback.comment || "", ratings_json: {} } }
    try {
      await apiFetch(`/candidates/${candidate.id}/status${candidate.search_id ? `?search_id=${candidate.search_id}` : ""}`, { method: "PATCH", body: JSON.stringify(body) }, token)
      toast.success("Estado actualizado")
      if (effectiveStatus === "rechazado") {
        onComposeMail({
          kind: "discard",
          candidate_id: candidate.id,
          search_id: candidate.search_id,
          reason: feedback.comment || feedback.main_reason
        })
      }
    } finally {
      setBusyAction("")
    }
  }

  async function presentToClient() {
    setBusyAction("candidate-present")
    try {
      const result = await apiFetch(`/candidates/${candidate.id}/present${candidate.search_id ? `?search_id=${candidate.search_id}` : ""}`, { method: "POST", body: JSON.stringify({}) }, token)
      onCandidatePatch?.({ is_presented_to_client: true, presented_at: result.presented_at })
      toast.success("Candidato presentado", candidate.full_name)
    } finally {
      setBusyAction("")
    }
  }

  async function replaceCv(file) {
    if (!file) return
    setBusyAction("candidate-cv-upload")
    const form = new FormData()
    form.append("file", file)
    try {
      const updated = await apiFetch(`/candidates/${candidate.id}/cv`, { method: "PATCH", body: form }, token)
      onCandidatePatch?.(updated)
    } finally {
      setBusyAction("")
    }
  }

  async function deleteCv() {
    const ok = await confirm({
      title: "¿Eliminar el CV?",
      description: "Se quitará el archivo y se perderá el análisis IA vinculado.",
      confirmLabel: "Eliminar CV",
      cancelLabel: "Cancelar",
      variant: "danger"
    })
    if (!ok) return
    setBusyAction("candidate-cv-delete")
    try {
      const updated = await apiFetch(`/candidates/${candidate.id}/cv`, { method: "DELETE" }, token)
      toast.success("CV eliminado", candidate.full_name)
      onCandidatePatch?.(updated)
    } finally {
      setBusyAction("")
    }
  }

  async function saveCandidateInfo() {
    setBusyAction("candidate-save")
    try {
      const updated = await apiFetch(`/candidates/${candidate.id}`, {
        method: "PATCH",
        body: JSON.stringify(candidateDraft)
      }, token)
      onCandidatePatch?.(updated)
      setEditingCandidate(false)
      toast.success("Datos guardados", candidateDraft.full_name)
    } catch (err) {
      toast.error("No se pudo guardar", err.message || "Error del servidor.")
    } finally {
      setBusyAction("")
    }
  }

  return (
    <div className="view-stack">
      <button className="ghost-action fit" onClick={onBack}>Volver</button>
      <section className="candidate-layout">
        <aside className="cv-panel">
          <h3>CV</h3>
          {candidate.cv_file_url ? (
            <>
              {(candidate.cv_file_name || "").toLowerCase().endsWith(".docx") && candidateCvHtml ? (
                <div className="cv-html-viewer" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(candidateCvHtml) }} />
              ) : (
                <PdfPreview fileUrl={candidate.cv_file_url} />
              )}
              <div className="cv-icon-row pill-row">
                <a className="icon-action mini" href={candidate.cv_file_url} target="_blank" rel="noreferrer" download aria-label="Descargar CV" title="Descargar CV">
                  <Icon name="download" size={18} />
                </a>
                {(role === "TALENT" || role === "SUPERADMIN") && (
                  <button type="button" className="icon-action mini danger-icon" onClick={deleteCv} aria-label={busyAction === "candidate-cv-delete" ? "Borrando CV" : "Eliminar CV"} title="Eliminar CV">
                    <Icon name="trash" size={18} />
                  </button>
                )}
              </div>
            </>
          ) : <Empty text="Este candidato no tiene CV cargado." />}
          {(role === "TALENT" || role === "SUPERADMIN") && (
            <label className="upload-line">
              {busyAction === "candidate-cv-upload" ? "Subiendo..." : "Subir nuevo CV"}
              <input type="file" accept="application/pdf" onChange={(event) => replaceCv(event.target.files?.[0])} />
            </label>
          )}
          <h3 className="notes-below-cv-heading">Notas internas</h3>
          <p className="hint" style={{ marginTop: 0, marginBottom: 8 }}>Escribí abajo; antes de guardar indicá qué roles o usuarios pueden ver la nota.</p>
          <div className="entity-list notes-mini-list">
            {(notes || []).map((note) => (
              <article key={note.id} className="entity-row compact-note-row">
                <div>
                  <strong>{note.author_name || `Usuario ${note.author_user_id}`}</strong>
                  <span className="muted small-meta">{formatDateTime(note.created_at)} · {(note.visible_roles || []).join(", ") || "Usuarios específicos"}</span>
                  <small className="muted">{note.body}</small>
                </div>
                {(role === "SUPERADMIN" || Number(note.author_user_id) === Number(readJson("user")?.id)) && (
                  <div className="row-actions">
                    <button type="button" className="icon-action mini" onClick={() => onEditNote(note.id, { body: `${note.body}\n`, visible_roles: note.visible_roles, visible_user_ids: note.visible_user_ids })} aria-label="Editar nota" title="Editar nota"><Icon name="edit" size={14} /></button>
                    <button type="button" className="icon-action mini" onClick={() => onDeleteNote(note.id)} aria-label="Eliminar nota" title="Eliminar nota"><Icon name="trash" size={14} /></button>
                  </div>
                )}
              </article>
            ))}
            {(!notes || notes.length === 0) && <span className="muted">Todavía no hay notas.</span>}
          </div>
          <div className="notes-paper">
            <textarea value={newNote} onChange={(event) => setNewNote(event.target.value)} placeholder="Nueva nota..." rows={6} aria-label="Texto de la nota" />
          </div>
          <div className="form-grid compact-form notes-form-below">
            <Field label="Visible para roles">
              <select multiple value={visibleRoles} size={4} onChange={(event) => setVisibleRoles(Array.from(event.target.selectedOptions).map((option) => option.value))}>
                <option value="TALENT">Talent</option>
                <option value="COMERCIAL">Comercial</option>
                <option value="CLIENTE">Cliente</option>
                <option value="SUPERADMIN">Administrador</option>
              </select>
            </Field>
            <Field label="Usuarios específicos (opcional)" helper="Mantené Ctrl/Cmd para elegir varios.">
              <select multiple value={visibleUserIds} onChange={(event) => setVisibleUserIds(Array.from(event.target.selectedOptions).map((option) => Number(option.value)))}>
                {users.map((item) => <option key={item.id} value={item.id}>{item.full_name || item.email} · {item.role}</option>)}
              </select>
            </Field>
            <button
              type="button"
              className="primary-action fit"
              onClick={async () => {
                if (!newNote.trim()) return
                await onAddNote({ body: newNote.trim(), visible_roles: visibleRoles, visible_user_ids: visibleUserIds })
                setNewNote("")
              }}
            >
              {busyAction === "note-save" ? "Guardando..." : "Guardar nota"}
            </button>
          </div>
        </aside>
        <div className="candidate-main">
          <div className="detail-hero compact candidate-detail-hero">
            <div className="candidate-hero-top">
              <p className="eyebrow">Candidato</p>
              {!editingCandidate ? (
                <>
                  <h2>{candidate.full_name}</h2>
                  <p className="candidate-short-profile">{candidate.short_profile || "Sin descripción cargada."}</p>
                </>
              ) : (
                <div className="form-grid">
                  <input value={candidateDraft.full_name} onChange={(event) => setCandidateDraft({ ...candidateDraft, full_name: event.target.value })} placeholder="Nombre completo" />
                  <input value={candidateDraft.email} onChange={(event) => setCandidateDraft({ ...candidateDraft, email: event.target.value })} placeholder="Email" />
                  <textarea rows={4} value={candidateDraft.short_profile} onChange={(event) => setCandidateDraft({ ...candidateDraft, short_profile: event.target.value })} placeholder="Resumen del perfil" />
                </div>
              )}
            </div>
            <div className="pill-row candidate-status-row">
              <StatusBadge status={candidate.status} />
              <CandidateAiBadge candidate={candidate} />
              {(role === "TALENT" || role === "SUPERADMIN") && (
                editingCandidate
                  ? (
                    <>
                      <button type="button" className="primary-action fit" onClick={saveCandidateInfo}>{busyAction === "candidate-save" ? "Guardando..." : "Guardar"}</button>
                      <button type="button" className="ghost-action" onClick={() => setEditingCandidate(false)}>Cancelar</button>
                    </>
                  )
                  : (
                    <button type="button" className="icon-action mini" onClick={() => setEditingCandidate(true)} aria-label="Editar candidato" title="Editar candidato">
                      <Icon name="edit" size={18} />
                    </button>
                  )
              )}
            </div>
          </div>
          <AiCandidatePanel candidate={candidate} busy={busyAction === "candidate-ai"} onReanalyze={onReanalyze} />
          <Panel
            title="Match IA vs. búsquedas relacionadas"
            subtitle="Puntaje y resumen cuando la IA comparó este perfil con una búsqueda concreta (contexto del puesto, no solo texto del CV)."
          >
            <div className="entity-list">
              {(searchAnalyses || []).map((item) => (
                <article key={`${item.search_id}-${item.candidate_id}`} className="entity-row">
                  <div>
                    <strong>{item.search_title || `Búsqueda ${item.search_id}`}</strong>
                    <span>{Math.round(Number(item.match_score || 0))}% · {capitalize(item.recommendation_level || "bajo")}</span>
                    <small className="muted">{item.summary || "Sin detalle del análisis."}</small>
                  </div>
                </article>
              ))}
              {(!searchAnalyses || searchAnalyses.length === 0) && <Empty text="No hay análisis por búsqueda disponibles para este candidato." />}
            </div>
          </Panel>
          {(role === "TALENT" || role === "SUPERADMIN" || role === "COMERCIAL") && (
            <Panel title="Presentación al cliente">
              <div className="pill-row">
                <span className="badge">{candidate.is_presented_to_client ? "Presentado" : "No presentado"}</span>
                {!candidate.is_presented_to_client && (
                  <button className="primary-action fit" onClick={presentToClient} disabled={busyAction === "candidate-present"}>
                    {busyAction === "candidate-present" ? "Presentando..." : "Presentar al cliente"}
                  </button>
                )}
              </div>
            </Panel>
          )}
          {(role === "TALENT" || role === "SUPERADMIN" || role === "COMERCIAL") && (
            <Panel title="Comunicación con candidato">
              <div className="pill-row">
                <button className="ghost-action" onClick={() => onComposeMail({ kind: "contact", candidate_id: candidate.id, search_id: candidate.search_id })}>Mail de contacto</button>
                <button className="ghost-action" onClick={() => onComposeMail({ kind: "advance", candidate_id: candidate.id, search_id: candidate.search_id })}>Mail de avance</button>
                <button className="ghost-action" onClick={() => onComposeMail({ kind: "interview_invite", candidate_id: candidate.id, search_id: candidate.search_id })}>Invitar a entrevista</button>
              </div>
            </Panel>
          )}
          {role === "CLIENTE" && candidate.is_presented_to_client && (
            <Panel title="Decisión del cliente">
              <div className="form-grid">
                <select value={status} onChange={(event) => setStatus(event.target.value)}>
                  <option value="en_revision">En revisión</option>
                  <option value="aprobado">Aprobado</option>
                  <option value="rechazado">Rechazado</option>
                </select>
                {status === "rechazado" && (
                  <select value={feedback.main_reason} onChange={(event) => setFeedback({ ...feedback, main_reason: event.target.value })}>
                    <option value="skills">Skills insuficientes</option>
                    <option value="experiencia">Experiencia no alineada</option>
                    <option value="cultural">Fit cultural</option>
                    <option value="otros">Otros</option>
                  </select>
                )}
                <textarea value={feedback.comment} onChange={(event) => setFeedback({ ...feedback, comment: event.target.value })} placeholder="Comentario opcional" />
                <button className="primary-action fit" onClick={saveStatus}>{busyAction === "candidate-status" ? "Guardando..." : "Guardar decisión"}</button>
              </div>
            </Panel>
          )}
          {role === "CLIENTE" && !candidate.is_presented_to_client && (
            <Panel title="Decisión del cliente">
              <Empty text="Este candidato aún no fue presentado formalmente por el equipo Talent." />
            </Panel>
          )}
          <Panel title="Entrevistas y grabación IA">
            <div className="entity-list">
              {interviews.map((interview) => (
                <article key={interview.id} className="entity-row">
                  <div>
                    <strong>{interview.candidate_name || candidate.full_name}</strong>
                    <span>{interview.start_datetime ? new Date(interview.start_datetime).toLocaleString("es-AR") : `Entrevista ${interview.id}`}</span>
                  </div>
                  <div className="row-actions">
                    <StatusBadge status={interview.status} type="interview" />
                    <button className="ghost-action" onClick={() => setSelectedInterview(interview)}>Abrir IA</button>
                  </div>
                </article>
              ))}
              {interviews.length === 0 && <Empty text="No hay entrevistas asociadas." />}
            </div>
            <div className="form-grid compact-form">
              <textarea value={recorder.transcript} onChange={(event) => setRecorder((prev) => ({ ...prev, transcript: event.target.value }))} placeholder="Pegá o editá la transcripción aquí..." rows={5} />
              <input type="file" accept=".txt,.docx" onChange={(event) => setUploadedTranscript(event.target.files?.[0] || null)} />
              <div className="pill-row">
                <button
                  className="ghost-action fit"
                  onClick={async () => {
                    if (!selectedInterview?.id || !recorder.transcript.trim()) return
                    await onSaveTranscript(selectedInterview.id, candidate.id, "manual_text", recorder.transcript.trim())
                  }}
                >
                  {busyAction === "transcript-save" ? "Guardando..." : "Guardar transcripción"}
                </button>
                <button
                  className="ghost-action fit"
                  onClick={async () => {
                    if (!selectedInterview?.id || !uploadedTranscript) return
                    const form = new FormData()
                    form.append("interview_id", selectedInterview.id)
                    form.append("candidate_id", candidate.id)
                    form.append("file", uploadedTranscript)
                    await uploadTranscript(form, token)
                  }}
                >
                  {busyAction === "transcript-upload" ? "Subiendo..." : "Subir transcripción"}
                </button>
              </div>
            </div>
          </Panel>
        </div>
      </section>
      {selectedInterview && (
        <InterviewModal
          interview={selectedInterview}
          role={role}
          recorder={recorder}
          setRecorder={setRecorder}
          busy={busyAction === "interview-ai"}
          onClose={() => setSelectedInterview(null)}
          onAnalyze={onAnalyzeInterview}
          onStartRecording={onStartRecording}
          onStopRecording={onStopRecording}
          onAnalyzeRecording={onAnalyzeRecording}
        />
      )}
    </div>
  )
}

function AiCandidatePanel({ candidate, busy, onReanalyze }) {
  const score = Number.isFinite(Number(candidate.ai_fit_score)) ? Math.round(Number(candidate.ai_fit_score)) : null
  return (
    <Panel title="IA de compatibilidad">
      <div className="ai-panel">
        <div className="ai-score">
          <strong>{score !== null ? `${score}%` : "N/D"}</strong>
          <span>{candidate.ai_fit_recommendation ? "Recomendado" : "Requiere revisión"}</span>
        </div>
        <div>
          <p>{candidate.ai_fit_summary || "Sin análisis IA todavía."}</p>
          <div className="tag-row">
            {(candidate.ai_fit_reasons || []).slice(0, 6).map((reason, index) => <span key={`${reason}-${index}`}>{reason}</span>)}
          </div>
          <button className="ghost-action" onClick={onReanalyze} disabled={busy}>{busy ? "Analizando..." : "Reanalizar IA"}</button>
        </div>
      </div>
    </Panel>
  )
}

function PdfPreview({ fileUrl }) {
  const wrapRef = useRef(null)
  const [width, setWidth] = useState(360)
  const [pages, setPages] = useState(0)
  const [error, setError] = useState("")

  useEffect(() => {
    const node = wrapRef.current
    if (!node) return undefined
    const update = () => setWidth(Math.max(280, Math.min(760, node.clientWidth - 24)))
    update()
    const observer = new ResizeObserver(update)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return (
    <div className="cv-pdf-viewer" ref={wrapRef}>
      {error && (
        <Feedback variant="error" title="No se pudo previsualizar el PDF">
          {error}
        </Feedback>
      )}
      <Document
        file={fileUrl}
        loading={<SkeletonList count={2} />}
        error={<Feedback variant="error">El visor no pudo cargar este PDF. Podés abrirlo o descargarlo desde los botones.</Feedback>}
        onLoadSuccess={({ numPages }) => {
          setPages(numPages || 0)
          setError("")
        }}
        onLoadError={(err) => setError(err?.message || "Archivo inválido o inaccesible.")}
      >
        {Array.from({ length: pages || 0 }, (_, index) => (
          <Page
            key={`page-${index + 1}`}
            pageNumber={index + 1}
            width={width}
            renderAnnotationLayer={false}
            renderTextLayer={false}
          />
        ))}
      </Document>
    </div>
  )
}

function AiQuestionsPanel({ search, busy, onReanalyze }) {
  const questions = search.ai_questions || []
  return (
    <Panel title="IA sobre Job Description">
      <div className="ai-questions">
        <div className="pill-row">
          <span className={search.ai_questions_needs_follow_up ? "badge warn" : "badge ok"}>
            {search.ai_questions_needs_follow_up ? "Pedir más información" : "Contexto suficiente"}
          </span>
          <button className="ghost-action" onClick={onReanalyze} disabled={busy}>{busy ? "Analizando..." : "Reanalizar JD"}</button>
        </div>
        <p>{search.ai_questions_summary || "La IA todavía no revisó esta búsqueda."}</p>
        {questions.length > 0 && (
          <ol>
            {questions.map((question, index) => <li key={`${question}-${index}`}>{question}</li>)}
          </ol>
        )}
      </div>
    </Panel>
  )
}

function InterviewModal({ interview, role, recorder, setRecorder, busy, onClose, onAnalyze, onStartRecording, onStopRecording, onAnalyzeRecording }) {
  const isActiveRecording = recorder.active && String(recorder.interviewId) === String(interview.id)
  const isCurrentRecording = String(recorder.interviewId) === String(interview.id)
  const roleContext = role === "CLIENTE" ? "client_interview" : "internal_interview"
  const currentTranscript = isCurrentRecording ? recorder.transcript || "" : ""

  function analyzeCurrentTranscript() {
    const text = currentTranscript.trim()
    if (text) onAnalyze(interview, roleContext, text)
    else onAnalyze(interview, roleContext)
  }

  function analyzeCurrentRecording() {
    if (currentTranscript.trim()) onAnalyze(interview, roleContext, currentTranscript)
    else onAnalyzeRecording()
  }

  return (
    <div className="modal-backdrop">
      <section className="modal-card">
        <div className="modal-head">
          <div>
            <p className="eyebrow">Entrevista</p>
            <h3>{interview.candidate_name || "Detalle"}</h3>
          </div>
          <button type="button" className="icon-action" onClick={onClose} aria-label="Cerrar entrevista"><Icon name="close" size={14} /></button>
        </div>
        <div className="recorder-panel">
          <div className="pill-row">
            {isActiveRecording ? (
              <button className="danger-action" onClick={onStopRecording}>Detener grabación</button>
            ) : (
              <button className="primary-action fit" onClick={() => onStartRecording(interview, roleContext)}>Iniciar grabación</button>
            )}
            <button className="ghost-action" onClick={analyzeCurrentTranscript} disabled={busy}>{busy ? "Analizando..." : "Analizar transcripción"}</button>
          </div>
          {isCurrentRecording && (
            <>
              <textarea value={recorder.transcript} onChange={(event) => setRecorder((prev) => ({ ...prev, transcript: event.target.value }))} placeholder="Transcripción automática o manual..." rows={6} />
              <div className="pill-row">
                <button className="primary-action fit" onClick={analyzeCurrentRecording} disabled={busy || currentTranscript.trim().length < 40}>
                  Analizar grabación
                </button>
                {recorder.audioUrl && <a className="ghost-action" href={recorder.audioUrl} download={`entrevista-${interview.id}.webm`}>Descargar audio</a>}
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  )
}

function UploadCandidate({ searchId, clients = [], searches = [], token, onUploaded }) {
  const toast = useToast()
  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [shortProfile, setShortProfile] = useState("")
  const [clientId, setClientId] = useState(clients[0]?.id || "")
  const [selectedSearchIds, setSelectedSearchIds] = useState(searchId ? [Number(searchId)] : [])
  const [file, setFile] = useState(null)
  const [errors, setErrors] = useState({})
  const [submitError, setSubmitError] = useState("")
  const [loading, setLoading] = useState(false)

  function validate() {
    const next = {}
    if (!fullName.trim()) next.fullName = "Ingresá el nombre completo del candidato."
    if (!file) next.file = "Subí el CV en PDF."
    if (email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      next.email = "Email inválido."
    }
    if (!searchId && !clientId && !selectedSearchIds.length) next.clientId = "Elegí un cliente o una búsqueda."
    return next
  }

  useEffect(() => {
    if (!clientId && clients[0]?.id) setClientId(clients[0].id)
  }, [clients, clientId])

  async function submit(event) {
    event.preventDefault()
    setSubmitError("")
    const v = validate()
    setErrors(v)
    if (Object.keys(v).length) return
    setLoading(true)
    try {
      const form = new FormData()
      form.append("full_name", fullName.trim())
      form.append("email", email.trim())
      form.append("short_profile", shortProfile)
      form.append("file", file)
      if (!searchId && clientId) form.append("client_id", String(clientId))
      if (!searchId && selectedSearchIds.length) form.append("search_ids", selectedSearchIds.join(","))
      const data = await apiFetch(searchId ? `/searches/${searchId}/candidates` : "/candidates", { method: "POST", body: form }, token)
      const ai = Number.isFinite(Number(data.ai_fit_score)) ? ` Match IA ${Math.round(Number(data.ai_fit_score))}%.` : ""
      toast.success("Candidato cargado", `${fullName.trim()} fue creado.${selectedSearchIds.length || searchId ? " Quedó asignado a búsqueda." : ""}${ai}`)
      setFullName("")
      setEmail("")
      setShortProfile("")
      setSelectedSearchIds(searchId ? [Number(searchId)] : [])
      setFile(null)
      setErrors({})
      onUploaded()
    } catch (err) {
      setSubmitError(err.message || "No se pudo cargar el candidato.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Panel title="Crear candidato">
      <form className="form-grid" onSubmit={submit} noValidate>
        {!searchId && (
          <Field label="Cliente base" required error={errors.clientId}>
            <select value={clientId} onChange={(event) => setClientId(event.target.value)}>
              <option value="">Seleccionar cliente</option>
              {clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
            </select>
          </Field>
        )}
        {!searchId && (
          <Field label="Asignar a búsquedas" helper="Opcional. Podés elegir varias con Ctrl/Cmd.">
            <select
              multiple
              size={Math.min(7, Math.max(3, searches.length || 3))}
              value={selectedSearchIds.map(String)}
              onChange={(event) => setSelectedSearchIds(Array.from(event.target.selectedOptions).map((option) => Number(option.value)))}
            >
              {searches.filter((search) => search.search_state !== "activa").map((search) => (
                <option key={search.id} value={search.id}>{search.title}</option>
              ))}
            </select>
          </Field>
        )}
        <Field label="Nombre completo" required error={errors.fullName}>
          <input
            value={fullName}
            onChange={(event) => { setFullName(event.target.value); if (errors.fullName) setErrors({ ...errors, fullName: "" }) }}
            placeholder="Ej: María González"
            autoComplete="name"
          />
        </Field>
        <Field label="Email del candidato" helper="Opcional · útil para futuras comunicaciones." error={errors.email}>
          <input
            type="email"
            value={email}
            onChange={(event) => { setEmail(event.target.value); if (errors.email) setErrors({ ...errors, email: "" }) }}
            onBlur={() => {
              if (email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
                setErrors((prev) => ({ ...prev, email: "Email inválido." }))
              }
            }}
            placeholder="candidato@dominio.com"
            inputMode="email"
            autoComplete="off"
          />
        </Field>
        <Field label="Resumen breve" helper="Quedará visible para el equipo y enriquece el análisis IA.">
          <textarea
            value={shortProfile}
            onChange={(event) => setShortProfile(event.target.value)}
            placeholder="Ej: 6 años en backend Node/Python, lideró equipo de 4 en fintech..."
            rows={3}
          />
        </Field>
        <Field label="CV del candidato" required error={errors.file}>
          <FileInput
            value={file}
            onChange={(value) => { setFile(value); if (errors.file) setErrors({ ...errors, file: "" }) }}
            accept="application/pdf"
            hint="Arrastrá un PDF o hacé click (máx. 10 MB)"
          />
        </Field>
        {submitError && <Feedback variant="error" title="No se pudo cargar">{submitError}</Feedback>}
        <button className="primary-action fit" disabled={loading} data-busy={loading || undefined}>
          <Icon name="upload" size={14} />
          {loading ? "Analizando..." : "Subir y analizar con IA"}
        </button>
      </form>
    </Panel>
  )
}

function CreateSearch({ token, clients, role, onCreated }) {
  const toast = useToast()
  const [clientId, setClientId] = useState(clients[0]?.id || "")
  const [title, setTitle] = useState("")
  const [jobDescription, setJobDescription] = useState("")
  const [documentFile, setDocumentFile] = useState(null)
  const [meetingFile, setMeetingFile] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState("")
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const [answers, setAnswers] = useState({})

  useEffect(() => {
    if (!clientId && clients[0]?.id) setClientId(clients[0].id)
  }, [clients, clientId])

  const stepIndex = result ? 2 : (clientId && title.trim() ? 1 : 0)

  async function submit(event) {
    event.preventDefault()
    setError("")
    setResult(null)
    const v = {}
    if (!clientId) v.clientId = "Elegí un cliente."
    if (!title.trim()) v.title = "Ingresá el título del puesto."
    if (!jobDescription.trim() && !documentFile) v.jobDescription = "Escribí la descripción o subí un PDF/DOCX."
    setErrors(v)
    if (Object.keys(v).length) {
      setError("Revisá los campos marcados para continuar.")
      return
    }
    setLoading(true)
    try {
      const form = new FormData()
      form.append("title", title.trim())
      form.append("job_description", jobDescription.trim())
      if (documentFile) form.append("file", documentFile)
      const data = await apiFetch(`/clients/${clientId}/searches`, { method: "POST", body: form }, token)
      if (meetingFile) {
        const meeting = new FormData()
        meeting.append("file", meetingFile)
        await apiFetch(`/searches/${data.id}/meeting-upload`, { method: "POST", body: meeting }, token).catch(() => null)
      }
      setResult(data)
      setTitle("")
      setJobDescription("")
      setDocumentFile(null)
      setMeetingFile(null)
      setErrors({})
      toast.success("Búsqueda creada", "Revisá las preguntas de la IA para enriquecer el perfil.")
    } catch (err) {
      setError(err.message || "No se pudo crear la búsqueda.")
    } finally {
      setLoading(false)
    }
  }

  async function answerQuestion(question) {
    const answer = answers[question.id]
    if (!answer?.trim()) return
    const updated = await apiFetch(`/searches/${result.id}/ai/questions/${question.id}/answer`, {
      method: "POST",
      body: formDataFrom({ answer: answer.trim() })
    }, token)
    setResult(updated)
    setAnswers((prev) => ({ ...prev, [question.id]: "" }))
  }

  async function skipQuestions() {
    if (!result) return
    await apiFetch(`/searches/${result.id}/ai/questions/skip`, { method: "POST" }, token)
    onCreated()
  }

  return (
    <section className="create-layout">
      <Panel title={role === "CLIENTE" ? "Nueva solicitud de búsqueda" : "Crear nueva búsqueda"}>
        <form className="form-grid" onSubmit={submit} noValidate>
          <Stepper steps={["Cliente y puesto", "Documento", "Revisión IA"]} current={stepIndex} />
          <Field label="Cliente" required error={errors.clientId}>
            <select
              value={clientId}
              onChange={(event) => { setClientId(event.target.value); if (errors.clientId) setErrors({ ...errors, clientId: "" }) }}
            >
              <option value="">Seleccionar cliente</option>
              {clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
            </select>
          </Field>
          <Field label="Título del puesto" required error={errors.title} helper="Cómo se mostrará en listados internos y externos.">
            <input
              value={title}
              onChange={(event) => { setTitle(event.target.value); if (errors.title) setErrors({ ...errors, title: "" }) }}
              placeholder="Ej: Senior Backend Engineer"
              autoComplete="off"
            />
          </Field>
          <Field
            label="Job description"
            required
            error={errors.jobDescription}
            helper="Pegá el texto o subí un PDF/DOCX. La IA puede usar ambos."
          >
            <textarea
              value={jobDescription}
              onChange={(event) => { setJobDescription(event.target.value); if (errors.jobDescription) setErrors({ ...errors, jobDescription: "" }) }}
              placeholder="Requisitos, contexto, seniority, stack, expectativas..."
              rows={10}
            />
          </Field>
          <Field label="Documento adjunto" helper="PDF o DOCX. Opcional si pegaste el texto arriba.">
            <FileInput
              value={documentFile}
              onChange={(value) => { setDocumentFile(value); if (errors.jobDescription) setErrors({ ...errors, jobDescription: "" }) }}
              accept="application/pdf,.docx"
              hint="Arrastrá un PDF o DOCX (máx. 10 MB)"
            />
          </Field>
          {role === "COMERCIAL" && (
            <Field label="Reunión con cliente" helper="Opcional — audio, video o PDF para enriquecer el análisis.">
              <FileInput
                value={meetingFile}
                onChange={setMeetingFile}
                accept="audio/*,video/*,.pdf,.docx"
                hint="Audio, video, PDF o DOCX"
              />
            </Field>
          )}
          {error && <Feedback variant="error" title="Revisá el formulario">{error}</Feedback>}
          <button className="primary-action fit" disabled={loading} data-busy={loading || undefined}>
            <Icon name="plus" size={14} />
            {loading ? "Creando..." : "Crear y revisar con IA"}
          </button>
        </form>
      </Panel>
      <Panel title="Preguntas de la IA" subtitle="Respondé o omití para finalizar.">
        {!result && (
          <EmptyState
            icon="info"
            title="Sin preguntas todavía"
            description="Al crear la búsqueda, la IA marcará si faltan datos clave del rol."
          />
        )}
        {result && (
          <div className="ai-questions">
            <Feedback variant="info">{result.ai_questions_summary || "La búsqueda fue creada."}</Feedback>
            <div className="question-card">
              <strong>Job Description generado</strong>
              <p dangerouslySetInnerHTML={{ __html: safeDescriptionHtml(result.job_description) }} />
            </div>
            {(result.ai_question_items || []).filter((item) => item.status === "pending").map((question) => (
              <div className="question-card" key={question.id}>
                <strong>{question.question}</strong>
                <textarea
                  value={answers[question.id] || ""}
                  onChange={(event) => setAnswers({ ...answers, [question.id]: event.target.value })}
                  placeholder="Tu respuesta..."
                  rows={3}
                  aria-label={`Respuesta para: ${question.question}`}
                />
                <button type="button" className="ghost-action fit" onClick={() => answerQuestion(question)} disabled={loading}>
                  <Icon name="check" size={14} />
                  {loading ? "Guardando..." : "Guardar respuesta"}
                </button>
              </div>
            ))}
            <div className="pill-row">
              <button type="button" className="primary-action fit" onClick={onCreated}>
                <Icon name="check" size={14} />
                Finalizar
              </button>
              <button type="button" className="ghost-action fit" onClick={skipQuestions} disabled={loading}>
                {loading ? "Procesando..." : "Omitir preguntas faltantes"}
              </button>
            </div>
          </div>
        )}
      </Panel>
    </section>
  )
}

function buildProposalEmailIntro({ fullName, searchTitle, notes, meetingUrl }) {
  const lines = [`Hola ${fullName || "candidato"},`, "", `Queremos coordinar una entrevista para ${searchTitle || "la búsqueda"}.`, ""]
  if (notes?.trim()) lines.push(notes.trim(), "")
  if (meetingUrl?.trim()) lines.push(`Link de reunión: ${meetingUrl.trim()}`, "")
  return lines.join("\n").trim()
}

function CalendarView({ token, clients, role, searches, candidates }) {
  const toast = useToast()
  const [events, setEvents] = useState([])
  const [inviteUsers, setInviteUsers] = useState([])
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [eventFilter, setEventFilter] = useState({ search_id: "", candidate_id: "" })
  const [proposal, setProposal] = useState({ candidate_id: "", search_id: "", title: "", notes: "", meeting_url: "", slots: [{ start_datetime: "", end_datetime: "" }] })
  const [proposalEmailIntro, setProposalEmailIntro] = useState("")
  const [proposalStep, setProposalStep] = useState("fields")
  const [draft, setDraft] = useState({ title: "", start_datetime: "", end_datetime: "", client_id: "", notes: "", meeting_url: "", invite_emails: "", invited_user_ids: [] })
  const [eventModalOpen, setEventModalOpen] = useState(false)
  const [proposalModalOpen, setProposalModalOpen] = useState(false)
  const [eventMessage, setEventMessage] = useState("")
  const [proposalError, setProposalError] = useState("")
  const [busy, setBusy] = useState("")

  const weekStart = startOfWeek(new Date())

  useEffect(() => {
    apiFetch("/calendar/events", {}, token).then(setEvents).catch(() => setEvents([]))
    apiFetch("/calendar/invite-users", {}, token).then(setInviteUsers).catch(() => setInviteUsers([]))
  }, [token])

  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)), [weekStart])
  const visibleEvents = useMemo(() => {
    const start = weekStart.getTime()
    const end = addDays(weekStart, 7).getTime()
    return (events || []).filter((item) => {
      const time = new Date(item.start_datetime).getTime()
      const bySearch = !eventFilter.search_id || String(item.search_id) === String(eventFilter.search_id)
      const byCandidate = !eventFilter.candidate_id || String(item.candidate_id) === String(eventFilter.candidate_id)
      return time >= start && time < end && bySearch && byCandidate
    })
  }, [events, weekStart, eventFilter])

  function openEventModal() {
    setEventMessage("")
    setEventModalOpen(true)
  }

  function openProposalModal() {
    setProposalError("")
    setProposalStep("fields")
    setProposalEmailIntro("")
    setProposalModalOpen(true)
  }

  async function createEvent(event) {
    event.preventDefault()
    setEventMessage("")
    setBusy("create-event")
    const payload = {
      title: draft.title,
      start_datetime: draft.start_datetime,
      end_datetime: draft.end_datetime,
      client_id: draft.client_id ? Number(draft.client_id) : null,
      notes: draft.notes || null,
      meeting_url: draft.meeting_url || null,
      invite_emails: draft.invite_emails.split(/[,\n;]/).map((item) => item.trim()).filter(Boolean),
      invited_user_ids: draft.invited_user_ids.map((item) => Number(item)),
      role_scope: role,
      kind: "manual"
    }
    try {
      const created = await apiFetch("/calendar/events", { method: "POST", body: JSON.stringify(payload) }, token)
      setEvents((prev) => [...prev, created].sort((a, b) => new Date(a.start_datetime) - new Date(b.start_datetime)))
      setDraft({ title: "", start_datetime: "", end_datetime: "", client_id: "", notes: "", meeting_url: "", invite_emails: "", invited_user_ids: [] })
      if (created.mails_sent > 0) {
        toast.success(created.mails_sent === 1 ? "Invitación enviada por mail." : `${created.mails_sent} invitaciones enviadas por mail.`)
      }
      if (created.mail_warnings?.length) {
        toast.warn("Algunos mails no se enviaron", created.mail_warnings.slice(0, 3).join(" · "))
      }
      setEventMessage(created.mails_sent > 0 ? "Evento creado e invitaciones enviadas." : "Evento creado.")
      setEventModalOpen(false)
    } catch (err) {
      setEventMessage(err.message || "No se pudo crear el evento.")
    } finally {
      setBusy("")
    }
  }

  async function deleteEvent(id) {
    await apiFetch(`/calendar/events/${id}`, { method: "DELETE" }, token)
    setEvents((prev) => prev.filter((item) => item.id !== id))
  }

  function validateProposalFields() {
    const slot_options = proposal.slots.filter((item) => item.start_datetime && item.end_datetime)
    if (!proposal.candidate_id) return "Elegí un candidato."
    if (!proposal.search_id) return "Elegí una búsqueda."
    if (!slot_options.length) return "Completá al menos un horario con inicio y fin."
    return ""
  }

  function goToProposalReview() {
    setProposalError("")
    const err = validateProposalFields()
    if (err) {
      setProposalError(err)
      return
    }
    const cand = (candidates || []).find((c) => String(c.id) === String(proposal.candidate_id))
    const sea = (searches || []).find((s) => String(s.id) === String(proposal.search_id))
    setProposalEmailIntro(buildProposalEmailIntro({
      fullName: cand?.full_name,
      searchTitle: sea?.title,
      notes: proposal.notes,
      meetingUrl: proposal.meeting_url
    }))
    setProposalStep("review")
  }

  async function sendProposalFinal() {
    setProposalError("")
    const slot_options = proposal.slots.filter((item) => item.start_datetime && item.end_datetime)
    const err = validateProposalFields()
    if (err) {
      setProposalError(err)
      return
    }
    if (!proposalEmailIntro.trim()) {
      setProposalError("El mensaje no puede estar vacío.")
      return
    }
    setBusy("proposal")
    try {
      const res = await createInterviewProposal({
        candidate_id: Number(proposal.candidate_id),
        search_id: Number(proposal.search_id),
        title: proposal.title || "Entrevista con cliente",
        notes: proposal.notes || null,
        meeting_url: proposal.meeting_url || null,
        slot_options,
        email_body_override: proposalEmailIntro.trim()
      }, token)
      toast.success(mailDeliveredUserMessage(res))
      setProposal({ candidate_id: "", search_id: "", title: "", notes: "", meeting_url: "", slots: [{ start_datetime: "", end_datetime: "" }] })
      setProposalEmailIntro("")
      setProposalStep("fields")
      setProposalModalOpen(false)
    } catch (e) {
      const msg = e.message || "No se pudo enviar la propuesta."
      setProposalError(msg)
      toast.error(msg)
    } finally {
      setBusy("")
    }
  }

  const eventForm = (
    <form className="form-grid" onSubmit={createEvent} noValidate>
      <Field label="Título" required>
        <input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} placeholder="Ej: Entrevista técnica" required />
      </Field>
      <Field label="Inicio" required>
        <input type="datetime-local" value={draft.start_datetime} onChange={(event) => setDraft({ ...draft, start_datetime: event.target.value })} required />
      </Field>
      <Field label="Fin" required>
        <input type="datetime-local" value={draft.end_datetime} onChange={(event) => setDraft({ ...draft, end_datetime: event.target.value })} required />
      </Field>
      <Field label="Cliente" helper="Opcional · útil para filtrar el calendario.">
        <select value={draft.client_id} onChange={(event) => setDraft({ ...draft, client_id: event.target.value })}>
          <option value="">Sin cliente específico</option>
          {clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
        </select>
      </Field>
      <Field label="Link de reunión" helper="Google Meet, Zoom u otro. Opcional.">
        <input value={draft.meeting_url} onChange={(event) => setDraft({ ...draft, meeting_url: event.target.value })} placeholder="https://meet.google.com/..." inputMode="url" />
      </Field>
      <Field label="Emails externos" helper="Separados por coma, salto de línea o punto y coma.">
        <textarea value={draft.invite_emails} onChange={(event) => setDraft({ ...draft, invite_emails: event.target.value })} placeholder="ana@empresa.com, juan@empresa.com" rows={2} />
      </Field>
      <Field label="Usuarios del sistema" helper="Mantené Ctrl/Cmd para seleccionar varios.">
        <select multiple value={draft.invited_user_ids} onChange={(event) => setDraft({ ...draft, invited_user_ids: Array.from(event.target.selectedOptions).map((option) => option.value) })}>
          {inviteUsers.map((item) => <option key={item.id} value={item.id}>{item.full_name || item.email} · {item.role}</option>)}
        </select>
      </Field>
      <Field label="Notas">
        <textarea value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} placeholder="Detalles, agenda, contexto..." rows={3} />
      </Field>
      {eventMessage && <Feedback variant={eventMessage.includes("creado") ? "success" : "error"}>{eventMessage}</Feedback>}
      <div className="pill-row">
        <button type="button" className="ghost-action" onClick={() => setEventModalOpen(false)}>Cancelar</button>
        <button className="primary-action fit" type="submit" disabled={busy === "create-event"} data-busy={busy === "create-event" || undefined}>
          <Icon name="calendar" size={14} />
          {busy === "create-event" ? "Guardando..." : "Guardar evento"}
        </button>
      </div>
    </form>
  )

  const proposalFieldsForm = (
    <div className="form-grid">
      <Field label="Búsqueda" required>
        <select value={proposal.search_id} onChange={(event) => setProposal({ ...proposal, search_id: event.target.value })}>
          <option value="">Seleccionar búsqueda</option>
          {(searches || []).map((search) => <option key={search.id} value={search.id}>{search.title}</option>)}
        </select>
      </Field>
      <Field label="Candidato" required>
        <select value={proposal.candidate_id} onChange={(event) => setProposal({ ...proposal, candidate_id: event.target.value })}>
          <option value="">Seleccionar candidato</option>
          {(candidates || []).map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.full_name}</option>)}
        </select>
      </Field>
      <Field label="Título de la entrevista" helper="Si lo dejás vacío usamos 'Entrevista con cliente'.">
        <input value={proposal.title} onChange={(event) => setProposal({ ...proposal, title: event.target.value })} placeholder="Ej: Primera ronda" />
      </Field>
      <Field label="Link de reunión" helper="Opcional.">
        <input value={proposal.meeting_url} onChange={(event) => setProposal({ ...proposal, meeting_url: event.target.value })} placeholder="https://meet.google.com/..." inputMode="url" />
      </Field>
      <Field label="Horarios propuestos" helper="El candidato podrá elegir uno.">
        <div style={{ display: "grid", gap: 10 }}>
          {proposal.slots.map((slot, index) => (
            <div className="proposal-slot-grid" key={index}>
              <input type="datetime-local" value={slot.start_datetime} onChange={(event) => setProposal((prev) => ({ ...prev, slots: prev.slots.map((item, idx) => idx === index ? { ...item, start_datetime: event.target.value } : item) }))} aria-label={`Inicio horario ${index + 1}`} />
              <input type="datetime-local" value={slot.end_datetime} onChange={(event) => setProposal((prev) => ({ ...prev, slots: prev.slots.map((item, idx) => idx === index ? { ...item, end_datetime: event.target.value } : item) }))} aria-label={`Fin horario ${index + 1}`} />
            </div>
          ))}
          <button type="button" className="ghost-action fit" onClick={() => setProposal((prev) => ({ ...prev, slots: [...prev.slots, { start_datetime: "", end_datetime: "" }] }))}>
            <Icon name="plus" size={14} />
            Agregar horario
          </button>
        </div>
      </Field>
      <Field label="Mensaje para el candidato (borrador)" helper="Texto que después podés editar en el paso siguiente.">
        <textarea value={proposal.notes} onChange={(event) => setProposal({ ...proposal, notes: event.target.value })} placeholder="Contexto, ubicación, modalidad..." rows={3} />
      </Field>
      {proposalError && <Feedback variant="error">{proposalError}</Feedback>}
      <div className="pill-row">
        <button type="button" className="ghost-action" onClick={() => setProposalModalOpen(false)}>Cancelar</button>
        <button type="button" className="primary-action fit" onClick={goToProposalReview}>
          Revisar mensaje y enviar
        </button>
      </div>
    </div>
  )

  const proposalReviewForm = (
    <div className="form-grid">
      <p className="hint">Este es el texto que encabeza el mail. Al enviar se añadirán abajo los horarios propuestos y los enlaces para que el candidato acepte o rechace.</p>
      <Field label="Mensaje del mail">
        <textarea value={proposalEmailIntro} onChange={(event) => setProposalEmailIntro(event.target.value)} rows={12} className="proposal-mail-preview" />
      </Field>
      {proposalError && <Feedback variant="error">{proposalError}</Feedback>}
      <div className="pill-row">
        <button type="button" className="ghost-action" onClick={() => setProposalStep("fields")}>Volver</button>
        <button type="button" className="primary-action fit" onClick={() => void sendProposalFinal()} disabled={busy === "proposal"} data-busy={busy === "proposal" || undefined}>
          <Icon name="mail" size={14} />
          {busy === "proposal" ? "Enviando..." : "Enviar invitación"}
        </button>
      </div>
    </div>
  )

  return (
    <section className="view-stack calendar-view-single">
      <Panel title="Calendario organizado" subtitle="Invitaciones y envío de mail: conectá Gmail desde Perfil.">
        <div className="calendar-toolbar calendar-toolbar-actions">
          <div className="pill-row calendar-action-buttons">
            <button type="button" className="primary-action fit" onClick={openEventModal}>
              <Icon name="calendar" size={14} />
              Nuevo evento
            </button>
            {(role === "TALENT" || role === "SUPERADMIN") && (
              <button type="button" className="ghost-action fit" onClick={openProposalModal}>
                <Icon name="mail" size={14} />
                Proponer entrevista
              </button>
            )}
          </div>
          <div className="pill-row calendar-filters">
            <strong className="calendar-week-label">Semana del {formatDate(weekStart)} al {formatDate(addDays(weekStart, 6))}</strong>
            <select value={eventFilter.search_id} onChange={(event) => setEventFilter((prev) => ({ ...prev, search_id: event.target.value }))}>
              <option value="">Todas las búsquedas</option>
              {(searches || []).map((search) => <option key={search.id} value={search.id}>{search.title}</option>)}
            </select>
            <select value={eventFilter.candidate_id} onChange={(event) => setEventFilter((prev) => ({ ...prev, candidate_id: event.target.value }))}>
              <option value="">Todos los candidatos</option>
              {(candidates || []).map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.full_name}</option>)}
            </select>
          </div>
        </div>
        <div className="week-calendar">
          {weekDays.map((day) => {
            const dayEvents = visibleEvents.filter((item) => isSameDay(new Date(item.start_datetime), day))
            return (
              <div key={day.toISOString()} className={isSameDay(day, new Date()) ? "week-day today" : "week-day"}>
                <div className="week-day-head">
                  <strong>{day.toLocaleDateString("es-AR", { weekday: "long" })}</strong>
                  <span>{formatDate(day)}</span>
                </div>
                <div className="week-day-events">
                  {dayEvents.map((item) => (
                    <article className={`week-event status-${item.status || "confirmed"}`} key={item.id}>
                      <time>{formatTime(item.start_datetime)} - {formatTime(item.end_datetime)}</time>
                      <button className="event-title-button" onClick={() => setSelectedEvent(item)}>{item.title}</button>
                      {item.notes && <small>{item.notes}</small>}
                      {item.meeting_url && <a href={item.meeting_url} target="_blank" rel="noreferrer">Abrir reunión</a>}
                      <button className="ghost-action fit" onClick={() => deleteEvent(item.id)}>Eliminar</button>
                    </article>
                  ))}
                  {dayEvents.length === 0 && <span className="muted">Sin eventos</span>}
                </div>
              </div>
            )
          })}
        </div>
        {events.length > 0 && visibleEvents.length === 0 && <Empty text="No hay eventos en esta semana." />}
      </Panel>
      {eventModalOpen && (
        <div className="modal-backdrop">
          <section className="modal-card modal-card-wide">
            <div className="modal-head">
              <div>
                <p className="eyebrow">Calendario</p>
                <h3>Crear evento</h3>
                <small className="muted">Si tenés Google conectado, puede sincronizarse.</small>
              </div>
              <button type="button" className="icon-action" onClick={() => setEventModalOpen(false)} aria-label="Cerrar"><Icon name="close" size={14} /></button>
            </div>
            {eventForm}
          </section>
        </div>
      )}
      {proposalModalOpen && (
        <div className="modal-backdrop">
          <section className="modal-card modal-card-wide">
            <div className="modal-head">
              <div>
                <p className="eyebrow">Calendario</p>
                <h3>Proponer entrevista al candidato</h3>
              </div>
              <button type="button" className="icon-action" onClick={() => setProposalModalOpen(false)} aria-label="Cerrar"><Icon name="close" size={14} /></button>
            </div>
            {proposalStep === "fields" ? proposalFieldsForm : proposalReviewForm}
          </section>
        </div>
      )}
      {selectedEvent && (
        <div className="modal-backdrop">
          <section className="modal-card">
            <div className="modal-head">
              <div>
                <p className="eyebrow">Evento de calendario</p>
                <h3>{selectedEvent.title}</h3>
              </div>
              <button type="button" className="icon-action" onClick={() => setSelectedEvent(null)} aria-label="Cerrar evento"><Icon name="close" size={14} /></button>
            </div>
            <div className="event-detail-grid">
              <div><strong>Inicio</strong><span>{new Date(selectedEvent.start_datetime).toLocaleString("es-AR")}</span></div>
              <div><strong>Fin</strong><span>{new Date(selectedEvent.end_datetime).toLocaleString("es-AR")}</span></div>
              {selectedEvent.notes && <div><strong>Notas</strong><span>{selectedEvent.notes}</span></div>}
              {selectedEvent.meeting_url && <div><strong>Reunión</strong><a href={selectedEvent.meeting_url} target="_blank" rel="noreferrer">{selectedEvent.meeting_url}</a></div>}
              {(selectedEvent.invite_emails || []).length > 0 && <div><strong>Emails invitados</strong><span>{selectedEvent.invite_emails.join(", ")}</span></div>}
              {(selectedEvent.invited_user_ids || []).length > 0 && (
                <div>
                  <strong>Usuarios del sistema</strong>
                  <span>{selectedEvent.invited_user_ids.map((id) => inviteUsers.find((item) => Number(item.id) === Number(id))?.email || `Usuario ${id}`).join(", ")}</span>
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </section>
  )
}

function TalentBankView({ token, searches, onRefresh, role }) {
  const toast = useToast()
  const confirm = useConfirm()
  const refreshParent = typeof onRefresh === "function" ? onRefresh : () => Promise.resolve()

  const isCommercialOnly = role === "COMERCIAL"

  const [items, setItems] = useState([])
  const [recommendations, setRecommendations] = useState([])
  const [searchId, setSearchId] = useState(searches[0]?.id || "")
  const [bankTab, setBankTab] = useState("active")
  const [draft, setDraft] = useState({ full_name: "", email: "", short_profile: "", file: null })
  const [editingId, setEditingId] = useState(null)
  const [editDraft, setEditDraft] = useState({ full_name: "", email: "", short_profile: "", file: null })
  const [quickAddOpen, setQuickAddOpen] = useState(false)
  const [bankMenuOpen, setBankMenuOpen] = useState(null)
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState("")
  const activeSearches = (searches || []).filter((search) => search.search_state === "activa")
  const assignableSearches = useMemo(
    () => (searches || []).filter((s) => !s.archived_at && s.manual_state !== "cerrada" && s.manual_state !== "desactivada"),
    [searches]
  )

  const [enBancaRows, setEnBancaRows] = useState([])
  const [enBancaLoading, setEnBancaLoading] = useState(true)
  const [busyEnBancaId, setBusyEnBancaId] = useState(null)

  useEffect(() => {
    if (isCommercialOnly) return
    apiFetch("/talent-bank/candidates", {}, token).then(setItems).catch(() => setItems([]))
  }, [token, isCommercialOnly])

  useEffect(() => {
    let live = true
    setEnBancaLoading(true)
    apiFetch("/candidates/bank/en-banca", {}, token)
      .then((data) => {
        if (live) setEnBancaRows(Array.isArray(data) ? data : [])
      })
      .catch(() => {
        toast.error("No se pudo cargar postulaciones en banca")
        if (live) setEnBancaRows([])
      })
      .finally(() => {
        if (live) setEnBancaLoading(false)
      })
    return () => { live = false }
  }, [token, toast])

  async function createCandidate(event) {
    event.preventDefault()
    setBusy("create-bank")
    const form = new FormData()
    form.append("full_name", draft.full_name)
    form.append("email", draft.email)
    form.append("short_profile", draft.short_profile)
    if (draft.file) form.append("file", draft.file)
    try {
      const created = await apiFetch("/talent-bank/candidates", { method: "POST", body: form }, token)
      setItems((prev) => [created, ...prev])
      setDraft({ full_name: "", email: "", short_profile: "", file: null })
      setQuickAddOpen(false)
      toast.success("Alta en banco", created.full_name || "Guardado.")
    } catch (err) {
      toast.error("No se pudo guardar", err.message || "Error")
    } finally {
      setBusy("")
    }
  }

  function startEdit(candidate) {
    setEditingId(candidate.id)
    setEditDraft({
      full_name: candidate.full_name || "",
      email: candidate.email || "",
      short_profile: candidate.short_profile || "",
      file: null
    })
  }

  async function saveEdit(candidateId) {
    setBusy(`edit-${candidateId}`)
    const form = new FormData()
    form.append("full_name", editDraft.full_name)
    form.append("email", editDraft.email)
    form.append("short_profile", editDraft.short_profile)
    if (editDraft.file) form.append("file", editDraft.file)
    try {
      const updated = await apiFetch(`/talent-bank/candidates/${candidateId}`, { method: "PATCH", body: form }, token)
      setItems((prev) => prev.map((item) => Number(item.id) === Number(candidateId) ? updated : item))
      setRecommendations((prev) => prev.map((item) => Number(item.id) === Number(candidateId) ? { ...item, ...updated } : item))
      setEditingId(null)
      setMessage("Candidato actualizado.")
    } finally {
      setBusy("")
    }
  }

  async function deleteCandidate(candidateId) {
    const ok = await confirm({
      title: "¿Pasar al banco como no activo?",
      description: "El candidato dejará de aparecer en recomendaciones para nuevas búsquedas.",
      confirmLabel: "Marcar no activo",
      cancelLabel: "Cancelar",
      variant: "warn"
    })
    if (!ok) return
    setBusy(`inactive-${candidateId}`)
    try {
      await apiFetch(`/talent-bank/candidates/${candidateId}`, { method: "DELETE" }, token)
      setItems((prev) => prev.map((item) => Number(item.id) === Number(candidateId) ? { ...item, status: "banco_no_activo" } : item))
      setRecommendations((prev) => prev.filter((item) => Number(item.id) !== Number(candidateId)))
      toast.success("Candidato actualizado", "Marcado como no activo en el banco.")
    } finally {
      setBusy("")
    }
  }

  async function activateCandidate(candidateId) {
    setBusy(`activate-${candidateId}`)
    try {
      const updated = await apiFetch(`/talent-bank/candidates/${candidateId}/activate`, { method: "POST" }, token)
      setItems((prev) => prev.map((item) => Number(item.id) === Number(candidateId) ? updated : item))
      setMessage("Candidato activado en banca.")
    } finally {
      setBusy("")
    }
  }

  async function recommend() {
    if (!searchId) return
    setBusy("recommend")
    try {
      const data = await apiFetch(`/talent-bank/recommend/${searchId}`, { method: "POST" }, token)
      setRecommendations(data.candidates || [])
    } finally {
      setBusy("")
    }
  }

  async function contact(candidateId) {
    setBusy(`contact-${candidateId}`)
    try {
      const data = await apiFetch(`/talent-bank/candidates/${candidateId}/contact`, { method: "POST", body: formDataFrom({ search_id: searchId }) }, token)
      toast.success(mailDeliveredUserMessage(data))
      setMessage(data.message || "Contacto enviado.")
    } catch (err) {
      toast.error(err.message || "No se pudo enviar el mail.")
      setMessage(err.message || "Error al enviar.")
    } finally {
      setBusy("")
    }
  }

  function formatCareerAppliedAt(iso) {
    if (!iso) return "—"
    try {
      return new Date(iso).toLocaleString("es-MX", { dateStyle: "short", timeStyle: "short" })
    } catch {
      return iso
    }
  }

  async function assignEnBancaCandidate(rowId, targetSearchId) {
    if (!targetSearchId) {
      toast.warn("Elegí una búsqueda", "Seleccioná una vacante activa.")
      return
    }
    setBusyEnBancaId(rowId)
    try {
      await apiFetch(`/candidates/${rowId}`, {
        method: "PATCH",
        body: JSON.stringify({ search_id: Number(targetSearchId) })
      }, token)
      toast.success("Candidato asignado a la búsqueda")
      setEnBancaRows((r) => r.filter((x) => x.id !== rowId))
      await refreshParent()
    } catch (e) {
      toast.error(e.message || "No se pudo asignar")
    } finally {
      setBusyEnBancaId(null)
    }
  }

  async function discardEnBancaCandidate(rowId) {
    setBusyEnBancaId(rowId)
    try {
      await apiFetch(`/candidates/${rowId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "descartado" })
      }, token)
      toast.success("Candidato descartado")
      setEnBancaRows((r) => r.filter((x) => x.id !== rowId))
      await refreshParent()
    } catch (e) {
      toast.error(e.message || "No se pudo descartar")
    } finally {
      setBusyEnBancaId(null)
    }
  }

  async function assignToSearch(candidateId) {
    if (!searchId || isCommercialOnly) return
    setBusy(`assign-${candidateId}`)
    try {
      await apiFetch(`/talent-bank/candidates/${candidateId}/assign-search/${searchId}`, { method: "POST" }, token)
      setItems((prev) => prev.filter((item) => Number(item.id) !== Number(candidateId)))
      setRecommendations((prev) => prev.filter((item) => Number(item.id) !== Number(candidateId)))
      setMessage("Candidato enviado a la búsqueda activa.")
    } finally {
      setBusy("")
    }
  }

  const activeItems = items.filter((item) => item.status !== "banco_no_activo")
  const inactiveItems = items.filter((item) => item.status === "banco_no_activo")
  const visibleRecommendations = recommendations.filter((item) => bankTab === "active" ? item.status !== "banco_no_activo" : item.status === "banco_no_activo")
  const bankItems = bankTab === "active" ? activeItems : inactiveItems
  const visible = recommendations.length ? visibleRecommendations : bankItems

  const careerPoolPanel = (
    <Panel title="Postulaciones sin búsqueda asignada" subtitle="Espontáneas desde career page pendientes de asignación">
      {enBancaLoading ? <SkeletonList count={4} /> : (
        <div className="entity-list">
          {enBancaRows.map((row) => (
            <article key={row.id} className="entity-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                <div>
                  <div style={{ fontWeight: 700 }}>{row.full_name}</div>
                  <div className="text-sm text-muted">{row.email || "Sin email"}</div>
                  <div className="text-xs text-muted" style={{ marginTop: 6 }}>{formatCareerAppliedAt(row.created_at)}</div>
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                  <select
                    aria-label="Asignar a búsqueda"
                    disabled={busyEnBancaId === row.id}
                    defaultValue=""
                    onChange={(e) => {
                      const v = e.target.value
                      e.target.value = ""
                      if (v) assignEnBancaCandidate(row.id, v)
                    }}
                    style={{ minWidth: 200 }}
                  >
                    <option value="">Asignar a búsqueda…</option>
                    {assignableSearches.map((s) => (
                      <option key={s.id} value={s.id}>{s.title}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="danger-action"
                    disabled={busyEnBancaId === row.id}
                    onClick={() => discardEnBancaCandidate(row.id)}
                  >
                    Descartar
                  </button>
                </div>
              </div>
              {row.short_profile ? (
                <p className="text-sm text-muted text-pre" style={{ margin: 0 }}>
                  {row.short_profile}
                </p>
              ) : null}
            </article>
          ))}
          {!enBancaRows.length && <Empty text="No hay candidatos en banca para tu organización." />}
        </div>
      )}
    </Panel>
  )

  return (
    <section className="view-stack">
      {careerPoolPanel}
      {!isCommercialOnly && (
      <Panel title="Banco de talento">
        <div className="pill-row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div className="tab-row">
            <button type="button" className={bankTab === "active" ? "tab-button active" : "tab-button"} onClick={() => setBankTab("active")}>Activos ({activeItems.length})</button>
            <button type="button" className={bankTab === "inactive" ? "tab-button active" : "tab-button"} onClick={() => setBankTab("inactive")}>No activos ({inactiveItems.length})</button>
          </div>
          <button type="button" className="ghost-action small fit" onClick={() => setQuickAddOpen((open) => !open)} title="Alta rápida al banco">
            <Icon name="plus" size={14} />
            {quickAddOpen ? "Cerrar alta" : "Alta rápida"}
          </button>
        </div>
        <div className="form-grid compact-form">
          <select value={searchId} onChange={(event) => setSearchId(event.target.value)}>
            <option value="">Elegir búsqueda para recomendar</option>
            {activeSearches.map((search) => <option key={search.id} value={search.id}>{search.title}</option>)}
          </select>
          <button type="button" className="primary-action fit" onClick={recommend}>{busy === "recommend" ? "Analizando..." : "Recomendar con IA"}</button>
          {message && <div className="hint">{message}</div>}
        </div>
        {quickAddOpen && (
          <form className="form-grid compact-form bank-quick-add" onSubmit={createCandidate}>
            <p className="eyebrow">Alta rápida</p>
            <input value={draft.full_name} onChange={(event) => setDraft({ ...draft, full_name: event.target.value })} placeholder="Nombre completo" required />
            <input value={draft.email} onChange={(event) => setDraft({ ...draft, email: event.target.value })} placeholder="Email" />
            <textarea value={draft.short_profile} onChange={(event) => setDraft({ ...draft, short_profile: event.target.value })} placeholder="Resumen del perfil" rows={3} />
            <input type="file" accept="application/pdf" onChange={(event) => setDraft({ ...draft, file: event.target.files?.[0] || null })} />
            <div className="pill-row">
              <button type="submit" className="primary-action fit">{busy === "create-bank" ? "Guardando..." : "Guardar en banco"}</button>
              <button type="button" className="ghost-action" onClick={() => setQuickAddOpen(false)}>Cancelar</button>
            </div>
          </form>
        )}
        <div className="entity-list">
          {visible.map((candidate) => (
            <article className={`entity-row bank-row ${bankMenuOpen === candidate.id ? "menu-open" : ""}`} key={candidate.id}>
              {editingId === candidate.id ? (
                <div className="bank-edit-form" style={{ gridColumn: "1 / -1" }}>
                  <input value={editDraft.full_name} onChange={(event) => setEditDraft({ ...editDraft, full_name: event.target.value })} placeholder="Nombre completo" />
                  <input value={editDraft.email} onChange={(event) => setEditDraft({ ...editDraft, email: event.target.value })} placeholder="Email" />
                  <textarea value={editDraft.short_profile} onChange={(event) => setEditDraft({ ...editDraft, short_profile: event.target.value })} placeholder="Resumen del perfil" />
                  <input type="file" accept="application/pdf" onChange={(event) => setEditDraft({ ...editDraft, file: event.target.files?.[0] || null })} />
                  <div className="pill-row">
                    <button type="button" className="primary-action fit" onClick={() => saveEdit(candidate.id)}>{busy === `edit-${candidate.id}` ? "Guardando..." : "Guardar"}</button>
                    <button type="button" className="ghost-action fit" onClick={() => setEditingId(null)}>Cancelar</button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="row-main">
                    <div className="bank-line-1">
                      <strong>{candidate.full_name}</strong>
                      {Number.isFinite(Number(candidate.recommended_score)) && (
                        <span className="badge warn">IA {Math.round(Number(candidate.recommended_score))}%</span>
                      )}
                    </div>
                    <span className="bank-meta">{candidate.email || "Sin email"}</span>
                    {candidate.recommended_summary && <small className="muted">{candidate.recommended_summary}</small>}
                    {candidate.recommended_recommendation !== undefined && (
                      <small className={candidate.recommended_recommendation ? "fit-text ok" : "fit-text danger"}>
                        {candidate.recommended_recommendation ? "Va para el puesto" : "No va para este puesto"}
                      </small>
                    )}
                    {candidate.short_profile && (
                      <small className="muted" style={{ display: "block", marginTop: 4 }}>{candidate.short_profile}</small>
                    )}
                  </div>
                  <div className="row-actions">
                    <div className="row-menu-wrap">
                      <button
                        type="button"
                        className="icon-action mini"
                        onClick={() => setBankMenuOpen((id) => (id === candidate.id ? null : candidate.id))}
                        aria-label="Más acciones del candidato en banca"
                        title="Más acciones"
                      >
                        ⋯
                      </button>
                      {bankMenuOpen === candidate.id && (
                        <div className="row-menu">
                          <button type="button" onClick={() => { contact(candidate.id); setBankMenuOpen(null) }} disabled={!searchId}>
                            {busy === `contact-${candidate.id}` ? "Enviando..." : "Contactar por mail"}
                          </button>
                          <button type="button" onClick={() => { assignToSearch(candidate.id); setBankMenuOpen(null) }} disabled={!searchId}>
                            {busy === `assign-${candidate.id}` ? "Enviando..." : "Enviar a búsqueda"}
                          </button>
                          <button type="button" onClick={() => { startEdit(candidate); setBankMenuOpen(null) }}>Editar</button>
                          {candidate.status === "banco_no_activo" ? (
                            <button type="button" onClick={() => { activateCandidate(candidate.id); setBankMenuOpen(null) }}>
                              {busy === `activate-${candidate.id}` ? "Activando..." : "Activar en banco"}
                            </button>
                          ) : (
                            <button type="button" onClick={() => { deleteCandidate(candidate.id); setBankMenuOpen(null) }}>
                              {busy === `inactive-${candidate.id}` ? "Guardando..." : "Marcar no activo"}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </>
              )}
            </article>
          ))}
          {visible.length === 0 && <Empty text="Todavía no hay candidatos en banco." />}
        </div>
      </Panel>
      )}
    </section>
  )
}

function BankRecommendations({ token, search }) {
  const toast = useToast()
  const [items, setItems] = useState([])
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState("")

  async function load() {
    setBusy("load")
    try {
      const data = await apiFetch(`/talent-bank/recommend/${search.id}`, { method: "POST" }, token)
      setItems(data.candidates || [])
    } finally {
      setBusy("")
    }
  }

  async function contact(candidateId) {
    setBusy(`contact-${candidateId}`)
    try {
      const data = await apiFetch(`/talent-bank/candidates/${candidateId}/contact`, { method: "POST", body: formDataFrom({ search_id: search.id }) }, token)
      toast.success(mailDeliveredUserMessage(data))
      setMessage(data.message || "Contacto enviado.")
    } catch (err) {
      toast.error(err.message || "No se pudo enviar el mail.")
      setMessage(err.message || "Error al enviar.")
    } finally {
      setBusy("")
    }
  }

  return (
    <Panel title="Recomendados desde banco">
      <div className="pill-row">
        <button className="primary-action fit" onClick={load}>{busy === "load" ? "Analizando..." : "Buscar recomendados IA"}</button>
        {message && <span className="hint">{message}</span>}
      </div>
      <div className="entity-list">
        {items.map((candidate) => (
          <article className="entity-row" key={candidate.id}>
            <div>
              <strong>{candidate.full_name}</strong>
              <span>Match IA {candidate.recommended_score || candidate.ai_fit_score || 0}%</span>
            </div>
            <button className="ghost-action" onClick={() => contact(candidate.id)}>{busy === `contact-${candidate.id}` ? "Enviando..." : "Contactar por mail"}</button>
          </article>
        ))}
        {items.length === 0 && <Empty text="Pedí recomendaciones para ver candidatos del banco." />}
      </div>
    </Panel>
  )
}

function ProfileSettings({ token, user, calendarConnection, setCalendarConnection, onConnectGoogle, googleConnecting }) {
  const toast = useToast()
  const oauthReady = calendarConnection?.oauth_configured === true
  const [smtpConfigured, setSmtpConfigured] = useState(false)
  const [prefs, setPrefs] = useState({
    default_stale_search_days: 14,
    default_no_response_days: 7,
    notification_settings: {},
    reminder_settings: {}
  })

  useEffect(() => {
    apiFetch("/me/email-settings", {}, token)
      .then((data) => setSmtpConfigured(Boolean(data.is_configured)))
      .catch(() => null)
    apiFetch("/me/preferences", {}, token)
      .then((data) => setPrefs((prev) => ({ ...prev, ...data })))
      .catch(() => null)
  }, [token])

  useEffect(() => {
    getGoogleCalendarStatus(token)
      .then((st) => setCalendarConnection(normalizeCalendarConnection(st)))
      .catch(() => setCalendarConnection(normalizeCalendarConnection(null)))
  }, [token, setCalendarConnection])

  async function useGoogleOnlyMail() {
    try {
      await apiFetch("/me/email-settings/use-google-only", { method: "POST" }, token)
      setSmtpConfigured(false)
      const st = await getGoogleCalendarStatus(token).catch(() => null)
      if (st) setCalendarConnection(normalizeCalendarConnection(st))
      toast.success("Listo: los envíos usarán tu Gmail conectado.")
    } catch (err) {
      toast.error(err.message || "No se pudo cambiar el canal de envío.")
    }
  }

  async function savePreferences() {
    try {
      await apiFetch("/me/preferences", {
        method: "PATCH",
        body: JSON.stringify({
          default_stale_search_days: Number(prefs.default_stale_search_days),
          default_no_response_days: Number(prefs.default_no_response_days),
          notification_settings: prefs.notification_settings,
          reminder_settings: prefs.reminder_settings
        })
      }, token)
      toast.success("Preferencias guardadas.")
    } catch (err) {
      toast.error(err.message || "No se pudieron guardar las preferencias.")
    }
  }

  async function disconnectCalendarProfile() {
    try {
      await disconnectGoogleCalendar(token)
      setCalendarConnection((prev) => ({
        ...prev,
        connected: false,
        google_email: "",
        expires_at: null,
        gmail_send_enabled: false,
        can_send_mail: false
      }))
      toast.success("Google desconectado.")
    } catch (err) {
      toast.error(err.message || "No se pudo desconectar.")
    }
  }

  return (
    <section className="content-grid two">
      <Panel title="Perfil">
        <div className="mini-list">
          <div className="mini-row"><span>Usuario</span><small>{user?.email}</small></div>
          <div className="mini-row"><span>Rol</span><small>{ROLE_LABELS[user?.role] || user?.role}</small></div>
        </div>
      </Panel>
      <Panel title="Correo y calendario">
        <div className="form-grid" style={{ gap: 14 }}>
          {!oauthReady && (
            <Feedback variant="warn" title="Google no disponible todavía">
              Tu administrador de la plataforma debe activar la integración con Google.
              Cuando esté lista, vas a poder conectar tu cuenta con un solo clic.
            </Feedback>
          )}
          <button
            type="button"
            className="primary-action fit"
            style={{ opacity: oauthReady ? undefined : 0.65 }}
            disabled={!oauthReady || googleConnecting}
            onClick={() => void onConnectGoogle()}
          >
            <Icon name="mail" size={16} />
            {googleConnecting ? "Conectando con Google…" : "Continuar con Google"}
          </button>
          <p className="muted text-sm" style={{ margin: 0 }}>
            Elegí tu cuenta de Google y aceptá los permisos. No hace falta configurar contraseñas ni servidores de correo.
          </p>
          {smtpConfigured && (
            <Feedback variant="warn">
              Tenés una configuración antigua de correo que puede interferir.{" "}
              <button type="button" className="ghost-action small fit" onClick={() => void useGoogleOnlyMail()}>
                Usar solo Google
              </button>
            </Feedback>
          )}
          {(calendarConnection?.connected || calendarConnection?.google_email) && (
            <div className="pill-row" style={{ flexWrap: "wrap", alignItems: "center" }}>
              <span className="badge ok">
                <Icon name="check" size={12} />
                {calendarConnection.google_email || "Sesión activa"}
              </span>
              {calendarConnection.gmail_send_enabled ? (
                <span className="badge ok"><Icon name="check" size={12} />Envío de correo activo</span>
              ) : (
                <span className="badge warn"><Icon name="clock" size={12} />Volvé a conectar si no podés enviar mail</span>
              )}
              <button type="button" className="ghost-action small fit" onClick={() => void disconnectCalendarProfile()}>
                Desconectar Google
              </button>
            </div>
          )}
        </div>
      </Panel>
      <Panel title="Alertas y recordatorios">
        <div className="form-grid compact-form">
          <Field label="Días sin movimiento (búsqueda)" htmlFor="pref-stale">
            <input
              id="pref-stale"
              type="number"
              min={1}
              value={prefs.default_stale_search_days}
              onChange={(e) => setPrefs((prev) => ({ ...prev, default_stale_search_days: e.target.value }))}
            />
          </Field>
          <Field label="Días sin respuesta (candidato)" htmlFor="pref-response">
            <input
              id="pref-response"
              type="number"
              min={1}
              value={prefs.default_no_response_days}
              onChange={(e) => setPrefs((prev) => ({ ...prev, default_no_response_days: e.target.value }))}
            />
          </Field>
          <button type="button" className="primary-action fit" onClick={() => void savePreferences()}>Guardar preferencias</button>
        </div>
      </Panel>
    </section>
  )
}

function MailComposerModal({ value, busy, canSendMail, oauthConfigured, googleConnecting, onConnectGoogle, onClose, onChange, onRegenerate, onSend }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section className="modal-card composer-card" role="dialog" aria-labelledby="composer-title" aria-modal="true">
        <div className="modal-head">
          <div>
            <p className="eyebrow">Redactor IA</p>
            <h3 id="composer-title">{mailKindLabel(value.kind)}</h3>
          </div>
          <button type="button" className="icon-action" onClick={onClose} aria-label="Cerrar redactor">
            <Icon name="close" size={14} />
          </button>
        </div>
        <div className="form-grid">
          {canSendMail === false && (
            <Feedback variant="warn" title="Conectá tu correo para enviar">
              {oauthConfigured ? (
                <>
                  Con un clic podés usar Gmail y calendario, sin configuración manual.{" "}
                  <button
                    type="button"
                    className="primary-action small fit"
                    disabled={googleConnecting}
                    onClick={() => void onConnectGoogle()}
                  >
                    {googleConnecting ? "Conectando…" : "Continuar con Google"}
                  </button>
                </>
              ) : (
                "El envío de correo no está disponible todavía. Contactá al administrador de la plataforma."
              )}
            </Feedback>
          )}
          <Field label="Asunto" required>
            <input
              value={value.subject || ""}
              onChange={(event) => onChange({ ...value, subject: event.target.value })}
              placeholder="Ej: Próximos pasos para tu postulación"
              autoFocus
            />
          </Field>
          <Field label="Contenido del mail" required>
            <textarea
              value={value.body || ""}
              onChange={(event) => onChange({ ...value, body: event.target.value })}
              placeholder="Contenido del mail"
              rows={12}
            />
          </Field>
          <Field label="Contexto para la IA" helper="Opcional · usalo para guiar el tono o agregar datos antes de regenerar.">
            <textarea
              value={value.extra_context || ""}
              onChange={(event) => onChange({ ...value, extra_context: event.target.value })}
              placeholder="Ej: Mantener tono más formal y mencionar reunión del miércoles."
              rows={4}
            />
          </Field>
          <div className="pill-row" style={{ justifyContent: "flex-end" }}>
            <button type="button" className="ghost-action" onClick={onRegenerate} disabled={busy} data-busy={busy || undefined}>
              <Icon name="refresh" size={14} />
              {busy ? "Procesando..." : "Regenerar"}
            </button>
            <button type="button" className="primary-action fit" onClick={onSend} disabled={busy} data-busy={busy || undefined}>
              <Icon name="mail" size={14} />
              {busy ? "Enviando..." : "Enviar"}
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}

function InterviewAnalysisModal({ value, busy, onChange, onClose, onAnalyze }) {
  const transcript = value.transcript || ""
  const result = value.result
  const transcriptError = transcript.trim() && transcript.trim().length < 40
    ? "Pegá al menos 40 caracteres para generar una devolución útil."
    : ""

  return (
    <div className="modal-backdrop" role="presentation" onClick={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section className="modal-card composer-card" role="dialog" aria-labelledby="interview-analysis-title" aria-modal="true">
        <div className="modal-head">
          <div>
            <p className="eyebrow">Entrevista IA</p>
            <h3 id="interview-analysis-title">Análisis de entrevista</h3>
          </div>
          <button type="button" className="icon-action" onClick={onClose} aria-label="Cerrar análisis de entrevista">
            <Icon name="close" size={14} />
          </button>
        </div>
        <div className="form-grid">
          <Field
            label="Transcripción"
            required
            helper="Pegá la transcripción completa o revisá el texto capturado por la grabación."
            error={transcriptError}
          >
            <textarea
              value={transcript}
              onChange={(event) => onChange({ ...value, transcript: event.target.value })}
              placeholder="Pegá acá la transcripción de la entrevista..."
              rows={9}
              autoFocus
            />
          </Field>
          <div className="pill-row" style={{ justifyContent: "flex-end" }}>
            <button
              type="button"
              className="primary-action fit"
              disabled={busy || transcript.trim().length < 40}
              data-busy={busy || undefined}
              onClick={() => onAnalyze(transcript)}
            >
              {busy ? "Analizando..." : "Analizar con IA"}
            </button>
          </div>
          {result && (
            <div className="panel panel-compact">
              <div className="metric-row">
                <div>
                  <span>Fit score</span>
                  <strong>{Math.round(Number(result.fit_score || 0))}%</strong>
                </div>
                <div>
                  <span>Decisión</span>
                  <strong>{result.recommendation ? "Recomendado" : "No recomendado"}</strong>
                </div>
              </div>
              <p className="text-sm text-muted" style={{ lineHeight: 1.6 }}>{result.summary || "Sin resumen generado."}</p>
              <Feedback variant="info" title="Feedback para Talent">
                {result.talent_feedback || "Sin comentario adicional."}
              </Feedback>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

function ClientCareerSection({ client, token, onUpdated }) {
  const toast = useToast()
  const [slug, setSlug] = useState(client.public_slug || "")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setSlug(client.public_slug || "")
  }, [client.id, client.public_slug])

  const previewBase = "https://aptia.it.com/careers/"
  const configured = Boolean(client.public_slug && String(client.public_slug).trim())

  async function save(e) {
    e.preventDefault()
    const v = slug.trim().toLowerCase()
    if (!/^[a-z0-9-]+$/.test(v)) {
      toast.warn("Slug inválido", "Solo letras minúsculas, números y guiones.")
      return
    }
    setBusy(true)
    try {
      const updated = await apiFetch(`/clients/${client.id}/slug`, {
        method: "PATCH",
        body: JSON.stringify({ public_slug: v })
      }, token)
      toast.success("Career page actualizada")
      onUpdated?.(updated)
    } catch (err) {
      toast.error(err.message || "No se pudo guardar")
    } finally {
      setBusy(false)
    }
  }

  function copyUrl() {
    if (!client.public_slug) {
      toast.warn("Guardá el slug primero")
      return
    }
    const url = `${previewBase}${client.public_slug}`
    navigator.clipboard.writeText(url).then(() => toast.success("URL copiada")).catch(() => toast.error("No se pudo copiar"))
  }

  return (
    <div className="panel panel-compact" style={{ border: "1px solid var(--line)" }}>
      <h4>Career Page</h4>
      <p className="text-sm text-muted" style={{ margin: "0 0 12px" }}>
        Estado: <strong>{configured ? "Activa" : "Sin configurar"}</strong>
      </p>
      <form className="form-grid" style={{ gap: 10 }} onSubmit={save}>
        <Field label="Slug (público)" helper="Solo a-z, 0-9 y guiones.">
          <input
            value={slug}
            onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
            placeholder="mi-empresa"
            autoComplete="off"
          />
        </Field>
        <p className="text-xs text-muted" style={{ margin: 0 }}>
          Vista previa: <code>{previewBase}{slug || "…"}</code>
        </p>
        <div className="pill-row">
          <button type="submit" className="primary-action fit" disabled={busy} data-busy={busy || undefined}>
            Guardar
          </button>
          <button type="button" className="ghost-action" onClick={copyUrl}>
            Copiar URL
          </button>
        </div>
      </form>
    </div>
  )
}

function AdminPanel({ users, clients, token, onRefresh }) {
  const toast = useToast()
  const confirm = useConfirm()
  const [draft, setDraft] = useState({
    full_name: "",
    email: "",
    password: "",
    role: "CLIENTE",
    client_id: "",
    must_change_password: false,
    is_active: true
  })
  const [errors, setErrors] = useState({})
  const [submitError, setSubmitError] = useState("")
  const [passwords, setPasswords] = useState({})
  const [busy, setBusy] = useState("")
  const [careerClientId, setCareerClientId] = useState(null)

  const pwdScore = passwordStrength(draft.password)
  const pwdLabel = !draft.password ? "" : pwdScore <= 1 ? "Baja" : pwdScore === 2 ? "Media" : "Fuerte"

  function validateCreate() {
    const next = {}
    if (!draft.email.trim()) next.email = "Email obligatorio."
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(draft.email.trim())) next.email = "Email inválido."
    if (!draft.password.trim()) next.password = "La contraseña inicial es obligatoria."
    else if (draft.password.length < 8) next.password = "Mínimo 8 caracteres."
    return next
  }

  async function createUser(event) {
    event.preventDefault()
    setSubmitError("")
    const v = validateCreate()
    setErrors(v)
    if (Object.keys(v).length) return
    setBusy("create")
    try {
      const clientId = draft.client_id ? Number(draft.client_id) : null
      await apiFetch("/admin/users", {
        method: "POST",
        body: JSON.stringify({
          full_name: draft.full_name.trim() || null,
          email: draft.email.trim(),
          password: draft.password,
          role: draft.role,
          client_id: draft.role === "CLIENTE" ? clientId : null,
          client_ids: draft.role === "COMERCIAL" || draft.role === "TALENT" ? (clientId ? [clientId] : []) : [],
          must_change_password: draft.must_change_password,
          is_active: draft.is_active
        })
      }, token)
      setDraft({ full_name: "", email: "", password: "", role: "CLIENTE", client_id: "", must_change_password: false, is_active: true })
      setErrors({})
      toast.success("Usuario creado", "Le enviamos el mail de bienvenida con la contraseña temporal.")
      await onRefresh()
    } catch (err) {
      setSubmitError(err.message || "No se pudo crear el usuario.")
    } finally {
      setBusy("")
    }
  }

  async function changePassword(user) {
    const newPassword = passwords[user.id]
    if (!newPassword?.trim()) {
      toast.warn("Falta la contraseña", "Ingresá la nueva contraseña antes de confirmar.")
      return
    }
    if (newPassword.length < 8) {
      toast.warn("Contraseña muy corta", "Mínimo 8 caracteres.")
      return
    }
    setBusy(`password-${user.id}`)
    try {
      await apiFetch(`/admin/users/${user.id}/change-password`, {
        method: "POST",
        body: JSON.stringify({ new_password: newPassword.trim() })
      }, token)
      setPasswords((prev) => ({ ...prev, [user.id]: "" }))
      toast.success("Contraseña actualizada", `Las sesiones activas de ${user.email} fueron cerradas.`)
      await onRefresh()
    } catch (err) {
      toast.error("No se pudo cambiar la contraseña", err.message || "Intentá de nuevo.")
    } finally {
      setBusy("")
    }
  }

  async function toggleActive(user) {
    setBusy(`active-${user.id}`)
    try {
      await apiFetch(`/admin/users/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !user.is_active })
      }, token)
      toast.success(user.is_active ? "Usuario desactivado" : "Usuario activado", user.email)
      await onRefresh()
    } catch (err) {
      toast.error("No se pudo actualizar el usuario", err.message || "Intentá de nuevo.")
    } finally {
      setBusy("")
    }
  }

  async function deleteUser(user) {
    const ok = await confirm({
      title: `Eliminar a ${user.email}`,
      description: "Esta acción es permanente. El historial queda anonimizado.",
      confirmLabel: "Eliminar definitivamente",
      cancelLabel: "Cancelar",
      variant: "danger",
      challenge: "ELIMINAR"
    })
    if (!ok) return
    setBusy(`delete-${user.id}`)
    try {
      await apiFetch(`/admin/users/${user.id}`, { method: "DELETE" }, token)
      toast.success("Usuario eliminado", user.email)
      await onRefresh()
    } catch (err) {
      toast.error("No se pudo eliminar", err.message || "Puede tener historial asociado.")
    } finally {
      setBusy("")
    }
  }

  return (
    <section className="view-stack">
      <section className="content-grid two">
        <Panel title="Crear usuario">
          <form className="form-grid" onSubmit={createUser} noValidate>
            <Field label="Nombre completo" helper="Cómo aparecerá en listados internos.">
              <input
                value={draft.full_name}
                onChange={(event) => setDraft({ ...draft, full_name: event.target.value })}
                placeholder="Ej: Ana Pérez"
                autoComplete="name"
              />
            </Field>
            <Field label="Email" required error={errors.email} helper="Recibirá el mail de bienvenida.">
              <input
                type="email"
                value={draft.email}
                onChange={(event) => { setDraft({ ...draft, email: event.target.value }); if (errors.email) setErrors({ ...errors, email: "" }) }}
                placeholder="usuario@dominio.com"
                inputMode="email"
                autoComplete="off"
              />
            </Field>
            <Field
              label="Contraseña inicial"
              required
              error={errors.password}
              helper={draft.password ? `Fuerza: ${pwdLabel} · ${draft.password.length >= 8 ? "OK" : "mínimo 8"}` : "Mínimo 8 caracteres. Sugerimos generar una temporal."}
            >
              <PasswordInput
                value={draft.password}
                onChange={(event) => { setDraft({ ...draft, password: event.target.value }); if (errors.password) setErrors({ ...errors, password: "" }) }}
                autoComplete="new-password"
                placeholder="Mínimo 8 caracteres"
              />
              {draft.password && <StrengthMeter score={pwdScore} />}
            </Field>
            <Field label="Rol">
              <select value={draft.role} onChange={(event) => setDraft({ ...draft, role: event.target.value })}>
                <option value="CLIENTE">Cliente</option>
                <option value="COMERCIAL">Comercial</option>
                <option value="TALENT">Talent</option>
                <option value="SUPERADMIN">Superadmin</option>
              </select>
            </Field>
            {draft.role !== "SUPERADMIN" && (
              <Field label="Cliente asociado" helper={draft.role === "CLIENTE" ? "Si lo dejás vacío, se crea uno automáticamente." : ""}>
                <select value={draft.client_id} onChange={(event) => setDraft({ ...draft, client_id: event.target.value })}>
                  <option value="">{draft.role === "CLIENTE" ? "Crear cliente automáticamente" : "Seleccionar cliente"}</option>
                  {clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
                </select>
              </Field>
            )}
            <fieldset style={{ border: "1px solid var(--line)", borderRadius: "var(--radius-md)", padding: "var(--space-3)", display: "grid", gap: 10 }}>
              <legend className="text-xs text-muted" style={{ padding: "0 6px", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em" }}>Opciones</legend>
              <label className="check-line">
                <input type="checkbox" checked={draft.must_change_password} onChange={(event) => setDraft({ ...draft, must_change_password: event.target.checked })} />
                Pedir cambio de contraseña al ingresar
              </label>
              <label className="check-line">
                <input type="checkbox" checked={draft.is_active} onChange={(event) => setDraft({ ...draft, is_active: event.target.checked })} />
                Usuario activo
              </label>
            </fieldset>
            {submitError && <Feedback variant="error" title="No se pudo crear el usuario">{submitError}</Feedback>}
            <button className="primary-action fit" disabled={busy === "create"} data-busy={busy === "create" || undefined}>
              <Icon name="plus" size={14} />
              {busy === "create" ? "Creando..." : "Crear usuario"}
            </button>
          </form>
        </Panel>
        <Panel title="Clientes">
          {clients.length === 0 ? (
            <EmptyState icon="users" title="Sin clientes cargados" description="Al crear usuarios cliente se generan automáticamente." />
          ) : (
            <div className="mini-list">
              {clients.map((client) => (
                <div key={client.id} className="mini-row" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, width: "100%" }}>
                    <div>
                      <span>{client.name}</span>
                      <small style={{ display: "block" }}>{client.status}</small>
                    </div>
                    <button
                      type="button"
                      className="ghost-action"
                      onClick={() => setCareerClientId((id) => (id === client.id ? null : client.id))}
                    >
                      {careerClientId === client.id ? "Ocultar detalle" : "Ver detalle"}
                    </button>
                  </div>
                  {careerClientId === client.id && (
                    <ClientCareerSection
                      client={client}
                      token={token}
                      onUpdated={async () => {
                        await onRefresh()
                      }}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </Panel>
      </section>
      <Panel title="Usuarios">
        {users.length === 0 ? (
          <EmptyState icon="users" title="No hay usuarios cargados" description="Empezá creando un usuario desde el formulario de arriba." />
        ) : (
          <div className="admin-user-list">
            {users.map((user) => (
              <article key={user.id} className="admin-user-card">
                <div>
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <Avatar name={user.full_name || user.email} />
                    <div>
                      <strong>{user.full_name || user.email}</strong>
                      <span style={{ display: "block", color: "var(--muted)" }}>{user.email}</span>
                    </div>
                  </div>
                  <div className="pill-row" style={{ marginTop: 10 }}>
                    <span className="badge">{user.role}</span>
                    <span className={user.is_active ? "badge ok" : "badge danger"}>
                      <Icon name={user.is_active ? "check" : "close"} size={12} />
                      {user.is_active ? "Activo" : "Desactivado"}
                    </span>
                    {user.must_change_password && (
                      <span className="badge warn">
                        <Icon name="clock" size={12} />
                        Debe cambiar contraseña
                      </span>
                    )}
                  </div>
                </div>
                <div className="admin-actions">
                  <Field label="Nueva contraseña" helper="Solo si querés resetearla.">
                    <PasswordInput
                      value={passwords[user.id] || ""}
                      onChange={(event) => setPasswords((prev) => ({ ...prev, [user.id]: event.target.value }))}
                      placeholder="Mínimo 8 caracteres"
                      autoComplete="new-password"
                    />
                  </Field>
                  <button type="button" className="ghost-action" onClick={() => changePassword(user)} disabled={busy === `password-${user.id}`} data-busy={busy === `password-${user.id}` || undefined}>
                    <Icon name="edit" size={14} />
                    {busy === `password-${user.id}` ? "Aplicando..." : "Cambiar contraseña"}
                  </button>
                  <button type="button" className="ghost-action" onClick={() => toggleActive(user)} disabled={busy === `active-${user.id}`}>
                    {user.is_active ? "Desactivar" : "Activar"}
                  </button>
                  <button type="button" className="danger-action" onClick={() => deleteUser(user)} disabled={busy === `delete-${user.id}`}>
                    <Icon name="trash" size={14} />
                    Eliminar
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </Panel>
    </section>
  )
}

function Panel({ title, children, subtitle = "" }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>{title}</h3>
          {subtitle ? <p className="panel-subtitle">{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </section>
  )
}

function DonutChart({ segments, centerValue, centerLabel }) {
  const total = segments.reduce((acc, item) => acc + Number(item.value || 0), 0)
  let cursor = 0
  const gradient = total > 0
    ? segments.filter((item) => item.value > 0).map((item) => {
        const start = (cursor / total) * 360
        cursor += Number(item.value || 0)
        const end = (cursor / total) * 360
        return `${item.color} ${start}deg ${end}deg`
      }).join(", ")
    : "#22304a 0deg 360deg"
  return (
    <div className="donut-wrap">
      <div className="donut" style={{ background: `conic-gradient(${gradient})` }}>
        <div><strong>{centerValue}</strong><span>{centerLabel}</span></div>
      </div>
      <div className="legend">
        {segments.map((item) => (
          <div key={item.key}><i style={{ background: item.color }} /> <span>{item.label}</span><strong>{item.value || 0}</strong></div>
        ))}
      </div>
    </div>
  )
}

function BarChart({ items, max, suffix = "", empty = "Sin datos." }) {
  if (!items.length) return <Empty text={empty} />
  const peak = max || Math.max(...items.map((item) => Number(item.value || 0)), 1)
  return (
    <div className="bar-chart">
      {items.map((item) => (
        <div key={item.key} className="bar-row">
          <div><span>{item.label}</span><strong>{item.value}{suffix}</strong></div>
          <div className="bar-track"><span style={{ width: `${Math.max(3, (Number(item.value || 0) / peak) * 100)}%`, background: item.color }} /></div>
        </div>
      ))}
    </div>
  )
}

const STATUS_ICON = {
  aprobado: "check",
  scheduled: "check",
  en_revision: "clock",
  pending: "clock",
  booked: "clock",
  entrevistado: "info",
  descartado: "close",
  cancelled: "close",
  canceled: "close",
  banco_talent: "users",
  banco_no_activo: "users",
  en_banca: "inbox",
  applied: "check"
}

function StatusBadge({ status, type = "candidate" }) {
  const label = type === "interview" ? interviewStatusLabel(status) : (STATUS_LABELS[status] || status || "Sin estado")
  const iconName = STATUS_ICON[status] || "info"
  return (
    <span className={`badge status-${status || "default"}`}>
      <Icon name={iconName} size={12} />
      {label}
    </span>
  )
}

function CandidateAiBadge({ candidate }) {
  const score = Number(candidate?.ai_fit_score)
  if (!Number.isFinite(score)) {
    return (
      <span className="badge muted-badge">
        <Icon name="clock" size={12} />
        IA pendiente
      </span>
    )
  }
  const ok = candidate.ai_fit_recommendation
  return (
    <span className={ok ? "badge ok" : "badge danger"}>
      <Icon name={ok ? "check" : "close"} size={12} />
      Match IA {Math.round(score)}%
    </span>
  )
}

function Empty({ text }) {
  return <EmptyState icon="inbox" title="Sin resultados" description={text} />
}

function readJson(key) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch (_) {
    return null
  }
}

function formDataFrom(values) {
  const form = new FormData()
  Object.entries(values || {}).forEach(([key, value]) => form.append(key, value ?? ""))
  return form
}

function startOfWeek(value) {
  const date = new Date(value)
  const day = date.getDay()
  const diff = day === 0 ? -6 : 1 - day
  date.setDate(date.getDate() + diff)
  date.setHours(0, 0, 0, 0)
  return date
}

function addDays(value, amount) {
  const date = new Date(value)
  date.setDate(date.getDate() + amount)
  return date
}

function isSameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}

function formatDate(value) {
  return new Date(value).toLocaleDateString("es-AR", { day: "2-digit", month: "short" })
}

function formatTime(value) {
  return new Date(value).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" })
}

function formatDateTime(value) {
  if (!value) return ""
  return new Date(value).toLocaleString("es-AR")
}

function buildStats(searches, candidates) {
  const byStatus = { en_revision: 0, entrevistado: 0, aprobado: 0, descartado: 0 }
  let aiTotal = 0
  let aiCount = 0
  for (const candidate of candidates || []) {
    if (byStatus[candidate.status] !== undefined) byStatus[candidate.status] += 1
    if (Number.isFinite(Number(candidate.ai_fit_score))) {
      aiTotal += Number(candidate.ai_fit_score)
      aiCount += 1
    }
  }
  return {
    searches: searches.length,
    candidates: candidates.length,
    approved: byStatus.aprobado,
    averageAi: aiCount ? Math.round(aiTotal / aiCount) : 0,
    byStatus
  }
}

function patchCandidateMap(map, candidateId, patch) {
  const next = {}
  for (const [searchId, list] of Object.entries(map || {})) {
    next[searchId] = (list || []).map((candidate) => Number(candidate.id) === Number(candidateId) ? { ...candidate, ...patch } : candidate)
  }
  return next
}

function patchCandidateList(list, candidateId, patch) {
  return (list || []).map((candidate) => Number(candidate.id) === Number(candidateId) ? { ...candidate, ...patch } : candidate)
}

function uniqueById(items) {
  return Array.from(new Map((items || []).map((item) => [item.id, item])).values())
}

function clientName(clients, clientId) {
  return clients.find((client) => String(client.id) === String(clientId))?.name || `Cliente ${clientId || ""}`
}

function groupSearchesByClient(searches) {
  const map = new Map()
  for (const search of searches || []) {
    const key = search.client_id || "none"
    map.set(key, (map.get(key) || 0) + 1)
  }
  return Array.from(map.entries()).map(([client_id, count]) => ({ client_id, count })).sort((a, b) => b.count - a.count)
}

function stripHtml(value) {
  return String(value || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim()
}

function normalizeDescriptionToHtml(value) {
  if (!value) return ""
  if (/<\/?[a-z][\s\S]*>/i.test(value)) return value
  return String(value).split("\n").map((line) => line.trim() ? `<p>${escapeHtml(line)}</p>` : "<br />").join("")
}

function safeDescriptionHtml(value) {
  return DOMPurify.sanitize(normalizeDescriptionToHtml(value))
}

function escapeHtml(value) {
  return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}

function truncate(value, max) {
  const text = String(value || "")
  return text.length > max ? `${text.slice(0, max).trim()}...` : text
}

function formatMatchPercent(item) {
  const raw = Number(item?.match_percentage ?? item?.match_score ?? 0)
  const percent = raw <= 10 ? raw * 10 : raw
  return `${Math.round(percent)}%`
}

function capitalize(value) {
  const text = String(value || "")
  if (!text) return ""
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}`
}

function mailKindLabel(kind) {
  const map = {
    contact: "Mail de contacto",
    discard: "Mail de descarte",
    advance: "Mail de avance",
    interview_invite: "Invitación a entrevista"
  }
  return map[kind] || "Mail"
}

function searchStateLabel(value) {
  const map = {
    abierta: "Abierta",
    activa: "Activa",
    desactivada: "Desactivada",
    eliminada: "Eliminada"
  }
  return map[value] || "Abierta"
}

function HubView({ token, role, clients }) {
  const [conversations, setConversations] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState("")
  const [newTitle, setNewTitle] = useState("")
  const [summary, setSummary] = useState(null)

  useEffect(() => {
    listConversations(token).then(setConversations).catch(() => setConversations([]))
  }, [token])

  useEffect(() => {
    if (!selectedId) return
    listMessages(selectedId, token).then(setMessages).catch(() => setMessages([]))
  }, [selectedId, token])

  async function createHubConversation() {
    if (!newTitle.trim()) return
    const row = await createConversation({
      conversation_type: role === "CLIENTE" ? "recruiter_client" : "internal_group",
      title: newTitle.trim(),
      client_id: clients?.[0]?.id || null,
      participant_user_ids: []
    }, token)
    setConversations((prev) => [row, ...prev])
    setSelectedId(row.id)
    setNewTitle("")
  }

  return (
    <section className="content-grid two">
      <Panel title="Conversaciones">
        <div className="form-grid compact-form">
          <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Nueva conversación" />
          <button type="button" className="primary-action fit" onClick={createHubConversation}>Crear</button>
        </div>
        <div className="entity-list">
          {conversations.map((row) => (
            <article key={row.id} className={`entity-row ${selectedId === row.id ? "selected-row" : ""}`} onClick={() => setSelectedId(row.id)} role="presentation">
              <div><strong>{row.title}</strong><small>{row.conversation_type}</small></div>
            </article>
          ))}
          {conversations.length === 0 && <Empty text="Sin conversaciones todavía." />}
        </div>
      </Panel>
      <Panel title="Mensajes">
        {!selectedId && <Empty text="Seleccioná una conversación." />}
        {selectedId && (
          <>
            <div className="entity-list" style={{ maxHeight: 320, overflow: "auto" }}>
              {messages.map((msg) => (
                <article key={msg.id} className="entity-row">
                  <div><strong>#{msg.sender_id}</strong><span>{msg.body}</span></div>
                </article>
              ))}
            </div>
            <div className="form-grid compact-form">
              <textarea rows={3} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Escribí un mensaje..." />
              <div className="pill-row">
                <button type="button" className="primary-action fit" onClick={async () => {
                  await sendMessage(selectedId, draft, token)
                  setDraft("")
                  setMessages(await listMessages(selectedId, token))
                }}>Enviar</button>
                {(role === "TALENT" || role === "COMERCIAL" || role === "SUPERADMIN") && (
                  <button type="button" className="ghost-action fit" onClick={async () => {
                    const result = await summarizeConversation(selectedId, token)
                    setSummary(result)
                  }}>Resumir con IA</button>
                )}
              </div>
              {summary && (
                <Feedback variant="info" title="Resumen IA">
                  {summary.summary}
                  {(summary.action_items || []).length > 0 && (
                    <ul>{summary.action_items.map((item, idx) => <li key={idx}>{item}</li>)}</ul>
                  )}
                </Feedback>
              )}
            </div>
          </>
        )}
      </Panel>
    </section>
  )
}

function titleFor(active) {
  const map = {
    overview: "Inicio",
    searches: "Búsquedas",
    candidates: "Candidatos",
    create: "Crear búsqueda",
    calendar: "Calendario",
    talentBank: "Banco de talento",
    profile: "Perfil",
    metrics: "Métricas",
    hub: "Hub",
    notifications: "Notificaciones",
    admin: "Administración"
  }
  return map[active] || "Atipia"
}

function topbarCopy(active, role) {
  const map = {
    overview: "Seguimiento rápido del estado general de la operación.",
    searches: "Gestioná búsquedas, prioridades y cambios de estado.",
    candidates: "Revisá perfiles, entrevistas, notas y acciones con IA.",
    create: "Abrí nuevas búsquedas con el contexto correcto desde el inicio.",
    calendar: "Coordiná agenda, entrevistas y eventos compartidos.",
    talentBank: "Banco interno, postulaciones desde career sin búsqueda y recomendaciones con IA.",
    profile: "Ajustá integraciones, correo y preferencias personales.",
    metrics: "Visualizá indicadores clave según tu rol y alcance.",
    notifications: "Revisá pendientes y mantené limpia tu bandeja.",
    admin: "Administrá usuarios, clientes y acceso operativo."
  }
  return map[active] || `Vista de ${ROLE_LABELS[role] || "usuario"}.`
}


function overviewCopy(role) {
  if (role === "CLIENTE") return { title: "Decidí más rápido con señales claras.", text: "Revisá candidatos, fit IA, entrevistas y feedback desde un tablero simple." }
  if (role === "TALENT") return { title: "Priorizá candidatos con inteligencia.", text: "Usá IA para saber qué perfiles encajan, qué preguntas faltan y cómo evolucionan las entrevistas." }
  if (role === "COMERCIAL") return { title: "Controlá búsquedas y cierres.", text: "Visualizá clientes, búsquedas abiertas, candidatos recomendados y oportunidades de cierre." }
  return { title: "Administrá el sistema.", text: "Gestioná usuarios, clientes y operación general del portal." }
}

function interviewStatusLabel(status) {
  const map = {
    pending: "Pendiente",
    booked: "Pendiente",
    scheduled: "Agendada",
    cancelled: "Cancelada",
    canceled: "Cancelada"
  }
  return map[String(status || "").toLowerCase()] || "Entrevista"
}

export default AppWithErrorBoundary
