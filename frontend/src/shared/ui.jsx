import React, { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState } from "react"

/* ============================================================
 * Icon — set de SVG inline consistentes (stroke 1.8-2, sin fill)
 * ============================================================ */

const ICON_PATHS = {
  check: (
    <path d="M5 12l5 5L20 7" />
  ),
  close: (
    <path d="M18 6 6 18M6 6l12 12" />
  ),
  alert: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 8v4M12 16h.01" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </>
  ),
  warning: (
    <>
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <path d="M12 9v4M12 17h.01" />
    </>
  ),
  successCircle: (
    <>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <path d="M22 4 12 14.01l-3-3" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
    </>
  ),
  bell: (
    <>
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </>
  ),
  refresh: (
    <>
      <path d="M23 4v6h-6" />
      <path d="M1 20v-6h6" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </>
  ),
  moon: (
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </>
  ),
  mail: (
    <>
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <path d="m22 6-10 7L2 6" />
    </>
  ),
  trash: (
    <>
      <path d="M3 6h18" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
    </>
  ),
  edit: (
    <>
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  arrowRight: <path d="M5 12h14M13 5l7 7-7 7" />,
  more: (
    <>
      <circle cx="12" cy="5" r="1.6" />
      <circle cx="12" cy="12" r="1.6" />
      <circle cx="12" cy="19" r="1.6" />
    </>
  ),
  upload: (
    <>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <path d="M17 8l-5-5-5 5" />
      <path d="M12 3v12" />
    </>
  ),
  download: (
    <>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </>
  ),
  file: (
    <>
      <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
      <path d="M13 2v7h7" />
    </>
  ),
  inbox: (
    <>
      <path d="M22 12h-6l-2 3h-4l-2-3H2" />
      <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
    </>
  ),
  calendar: (
    <>
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
    </>
  ),
  users: (
    <>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13A4 4 0 0 1 16 11" />
    </>
  ),
  logout: (
    <>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="M16 17l5-5-5-5" />
      <path d="M21 12H9" />
    </>
  ),
  eye: (
    <>
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  eyeOff: (
    <>
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <path d="M1 1l22 22" />
    </>
  ),
  menu: (
    <>
      <path d="M4 6h16M4 12h16M4 18h16" />
    </>
  )
}

export function Icon({ name, size = 16, className = "", ...rest }) {
  const path = ICON_PATHS[name]
  if (!path) return null
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={className}
      {...rest}
    >
      {path}
    </svg>
  )
}

/* ============================================================
 * Field — input/textarea/select con label, helper, error inline
 * ============================================================ */

export function Field({
  label,
  required = false,
  helper = "",
  error = "",
  hint = null,
  children,
  htmlFor
}) {
  const autoId = useId()
  const fieldId = htmlFor || autoId
  const helperId = helper ? `${fieldId}-helper` : undefined
  const errorId = error ? `${fieldId}-error` : undefined
  const describedBy = [helperId, errorId].filter(Boolean).join(" ") || undefined

  const childArray = React.Children.toArray(children)
  const enhanced = childArray.map((child, idx) => {
    if (!React.isValidElement(child)) return child
    if (idx > 0) return child
    return React.cloneElement(child, {
      id: child.props.id || fieldId,
      "aria-required": required || undefined,
      "aria-invalid": error ? true : undefined,
      "aria-describedby": describedBy
    })
  })

  return (
    <div className={`field${error ? " has-error" : ""}`}>
      {(label || hint) && (
        <div className="field-label-row">
          {label && (
            <label className="field-label" htmlFor={fieldId}>
              {label}
              {required && <span className="req" aria-hidden="true">*</span>}
            </label>
          )}
          {hint}
        </div>
      )}
      {enhanced}
      {helper && !error && (
        <small className="field-helper" id={helperId}>{helper}</small>
      )}
      {error && (
        <div className="field-error" id={errorId} role="alert">
          <Icon name="alert" size={14} />
          {error}
        </div>
      )}
    </div>
  )
}

/* ============================================================
 * Password input con show/hide
 * ============================================================ */

export function PasswordInput({ value, onChange, autoComplete = "current-password", placeholder, ...rest }) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="pwd-wrap">
      <input
        type={visible ? "text" : "password"}
        value={value}
        onChange={onChange}
        autoComplete={autoComplete}
        placeholder={placeholder}
        {...rest}
      />
      <button
        type="button"
        className="pwd-toggle"
        aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"}
        aria-pressed={visible}
        onClick={() => setVisible((v) => !v)}
      >
        {visible ? "Ocultar" : "Mostrar"}
      </button>
    </div>
  )
}

export function passwordStrength(value) {
  const v = String(value || "")
  if (!v) return 0
  let score = 0
  if (v.length >= 8) score += 1
  if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score += 1
  if (/\d/.test(v)) score += 1
  if (/[^A-Za-z0-9]/.test(v)) score += 1
  return Math.min(score, 3)
}

export function StrengthMeter({ score }) {
  const filled = Math.max(0, Math.min(3, score))
  const cls = filled === 0 ? "" : filled === 1 ? "s-1" : filled === 2 ? "s-2" : "s-3"
  return (
    <div className="strength-meter" aria-hidden="true">
      <span className={filled >= 1 ? cls : ""} />
      <span className={filled >= 2 ? cls : ""} />
      <span className={filled >= 3 ? cls : ""} />
    </div>
  )
}

/* ============================================================
 * FileInput estilado (replaces native input[type=file])
 * ============================================================ */

export function FileInput({ value, onChange, accept, multiple = false, label = "Elegir archivo", hint = "" }) {
  const inputRef = useRef(null)
  const [drag, setDrag] = useState(false)
  const fileName = value
    ? Array.isArray(value)
      ? value.map((f) => f.name).join(", ")
      : value.name
    : ""

  function pickFile(event) {
    const files = Array.from(event.target.files || [])
    if (!files.length) return
    onChange(multiple ? files : files[0])
  }

  function onDrop(event) {
    event.preventDefault()
    setDrag(false)
    const files = Array.from(event.dataTransfer.files || [])
    if (!files.length) return
    onChange(multiple ? files : files[0])
  }

  return (
    <label
      className={`file-input${drag ? " drag" : ""}`}
      onDragOver={(event) => { event.preventDefault(); setDrag(true) }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
    >
      <span className="file-cta">{label}</span>
      <span className="file-meta">
        {fileName || hint || "Arrastrá un archivo o hacé click"}
      </span>
      {value && (
        <button
          type="button"
          className="file-clear"
          aria-label="Quitar archivo"
          onClick={(event) => {
            event.preventDefault()
            event.stopPropagation()
            onChange(null)
            if (inputRef.current) inputRef.current.value = ""
          }}
        >
          <Icon name="close" size={16} />
        </button>
      )}
      <input
        ref={inputRef}
        type="file"
        hidden
        accept={accept}
        multiple={multiple}
        onChange={pickFile}
      />
    </label>
  )
}

/* ============================================================
 * Skeleton
 * ============================================================ */

export function Skeleton({ width = "100%", height = 12, radius = "var(--radius-md)", style = {} }) {
  return (
    <span
      className="skeleton"
      style={{ width, height, borderRadius: radius, ...style }}
      aria-hidden="true"
    />
  )
}

export function SkeletonRow() {
  return (
    <div className="skeleton-row" aria-hidden="true">
      <Skeleton width={32} height={32} radius="999px" />
      <div className="col">
        <Skeleton width="55%" />
        <Skeleton width="30%" />
      </div>
      <Skeleton width={64} height={24} radius="999px" />
    </div>
  )
}

export function SkeletonList({ rows = 3 }) {
  return (
    <div className="entity-list" aria-busy="true">
      {Array.from({ length: rows }).map((_, idx) => <SkeletonRow key={idx} />)}
    </div>
  )
}

/* ============================================================
 * Toast (context + provider + hook)
 * ============================================================ */

const ToastContext = createContext({ push: () => {}, dismiss: () => {} })
let toastSeq = 0

export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const timersRef = useRef({})

  const dismiss = useCallback((id) => {
    setItems((prev) => prev.filter((item) => item.id !== id))
    const timer = timersRef.current[id]
    if (timer) {
      clearTimeout(timer)
      delete timersRef.current[id]
    }
  }, [])

  const push = useCallback((toast) => {
    const id = `t${++toastSeq}`
    const payload = {
      id,
      variant: toast.variant || "info",
      title: toast.title || "",
      description: toast.description || "",
      duration: toast.duration ?? 4500
    }
    setItems((prev) => [...prev, payload])
    if (payload.duration > 0) {
      timersRef.current[id] = setTimeout(() => dismiss(id), payload.duration)
    }
    return id
  }, [dismiss])

  useEffect(() => () => {
    Object.values(timersRef.current).forEach(clearTimeout)
  }, [])

  const value = useMemo(() => ({
    push,
    dismiss,
    success: (title, description) => push({ variant: "success", title, description }),
    error: (title, description) => push({ variant: "error", title, description }),
    info: (title, description) => push({ variant: "info", title, description }),
    warn: (title, description) => push({ variant: "warn", title, description })
  }), [push, dismiss])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" role="region" aria-live="polite" aria-label="Notificaciones">
        {items.map((item) => (
          <div key={item.id} className={`toast-card ${item.variant}`}>
            <span className="t-icon">
              <Icon name={iconForVariant(item.variant)} size={16} />
            </span>
            <div className="t-body">
              {item.title && <strong>{item.title}</strong>}
              {item.description && <span>{item.description}</span>}
            </div>
            <button
              type="button"
              className="t-close"
              aria-label="Cerrar notificación"
              onClick={() => dismiss(item.id)}
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}

function iconForVariant(variant) {
  if (variant === "success") return "successCircle"
  if (variant === "error") return "alert"
  if (variant === "warn") return "warning"
  return "info"
}

/* ============================================================
 * Confirm dialog (context + hook)
 * ============================================================ */

const ConfirmContext = createContext({ confirm: async () => false })

export function ConfirmProvider({ children }) {
  const [state, setState] = useState(null)
  const resolverRef = useRef(null)

  const confirm = useCallback((options) => {
    return new Promise((resolve) => {
      resolverRef.current = resolve
      setState({
        title: options.title || "¿Confirmar acción?",
        description: options.description || "",
        confirmLabel: options.confirmLabel || "Confirmar",
        cancelLabel: options.cancelLabel || "Cancelar",
        variant: options.variant || "danger",
        challenge: options.challenge || null
      })
    })
  }, [])

  function close(result) {
    const resolver = resolverRef.current
    resolverRef.current = null
    setState(null)
    if (resolver) resolver(result)
  }

  useEffect(() => {
    if (!state) return
    function onKey(event) {
      if (event.key === "Escape") close(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [state])

  const value = useMemo(() => ({ confirm }), [confirm])

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      {state && (
        <ConfirmDialog
          state={state}
          onCancel={() => close(false)}
          onConfirm={() => close(true)}
        />
      )}
    </ConfirmContext.Provider>
  )
}

function ConfirmDialog({ state, onCancel, onConfirm }) {
  const [challenge, setChallenge] = useState("")
  const challengeNeeded = state.challenge
  const challengeOk = !challengeNeeded || challenge.trim() === challengeNeeded
  const iconName = state.variant === "warn" ? "warning" : state.variant === "info" ? "info" : "warning"
  const confirmClass = state.variant === "danger" ? "danger-action" : "primary-action"

  return (
    <div className="modal-backdrop" role="presentation" onClick={(event) => {
      if (event.target === event.currentTarget) onCancel()
    }}>
      <section
        className="confirm-card"
        role="alertdialog"
        aria-labelledby="confirm-title"
        aria-describedby="confirm-desc"
      >
        <div className="confirm-head">
          <div className={`confirm-icon ${state.variant}`}>
            <Icon name={iconName} size={16} />
          </div>
          <div>
            <h3 id="confirm-title">{state.title}</h3>
            {state.description && <p id="confirm-desc">{state.description}</p>}
          </div>
        </div>
        {challengeNeeded && (
          <Field
            label={<>Para confirmar, escribí <code style={{ color: "var(--red)" }}>{challengeNeeded}</code></>}
          >
            <input
              autoFocus
              value={challenge}
              onChange={(event) => setChallenge(event.target.value)}
              placeholder={challengeNeeded}
            />
          </Field>
        )}
        <div className="confirm-actions">
          <button type="button" className="ghost-action" onClick={onCancel}>
            {state.cancelLabel}
          </button>
          <button
            type="button"
            className={confirmClass}
            disabled={!challengeOk}
            onClick={onConfirm}
            autoFocus={!challengeNeeded}
          >
            {state.variant === "danger" && <Icon name="trash" size={14} />}
            {state.confirmLabel}
          </button>
        </div>
      </section>
    </div>
  )
}

export function useConfirm() {
  return useContext(ConfirmContext).confirm
}

/* ============================================================
 * Inline feedback (banner)
 * ============================================================ */

export function Feedback({ variant = "info", title, children }) {
  return (
    <div className={`feedback ${variant}`} role={variant === "error" ? "alert" : "status"}>
      <Icon name={iconForVariant(variant)} size={14} />
      <div>
        {title && <strong>{title}</strong>}
        {children}
      </div>
    </div>
  )
}

/* ============================================================
 * Stepper
 * ============================================================ */

export function Stepper({ steps, current = 0 }) {
  return (
    <div className="stepper" aria-label="Progreso del formulario">
      {steps.map((label, idx) => {
        const status = idx < current ? "done" : idx === current ? "active" : ""
        return (
          <React.Fragment key={label}>
            <div className={`step ${status}`}>
              <span className="dot">
                {idx < current ? <Icon name="check" size={12} /> : idx + 1}
              </span>
              {label}
            </div>
            {idx < steps.length - 1 && <span className="sep" />}
          </React.Fragment>
        )
      })}
    </div>
  )
}

/* ============================================================
 * EmptyState rich
 * ============================================================ */

export function EmptyState({ icon = "inbox", title, description, action }) {
  return (
    <div className="empty-state rich" role="status">
      <div className="empty-illu">
        <Icon name={icon} size={18} />
      </div>
      {title && <strong>{title}</strong>}
      {description && <span>{description}</span>}
      {action && <div className="empty-cta">{action}</div>}
    </div>
  )
}

/* ============================================================
 * Avatar
 * ============================================================ */

export function Avatar({ name = "", size = "md" }) {
  const initials = useMemo(() => {
    const parts = String(name || "").trim().split(/\s+/).filter(Boolean)
    if (!parts.length) return "·"
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  }, [name])
  const cls = size === "sm" ? "avatar sm" : size === "lg" ? "avatar lg" : "avatar"
  return <span className={cls} aria-hidden="true">{initials}</span>
}
