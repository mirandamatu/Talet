export class PlanLimitError extends Error {
  constructor(detail) {
    super(
      typeof detail === "object" && detail?.code === "trial_expired"
        ? "El período de prueba ha finalizado."
        : "Se alcanzó el límite de tu plan."
    )
    this.name = "PlanLimitError"
    this.payload = detail
  }
}

export const API = "/api"

/** FastAPI puede devolver detail como string o lista de errores de validación */
export function formatApiErrorDetail(detail) {
  if (detail == null || detail === "") return "Error"
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        if (typeof e === "string") return e
        if (e && typeof e === "object" && e.msg) {
          const loc = (e.loc || []).filter((part) => typeof part === "string" && part !== "body").join(".")
          return loc ? `${loc}: ${e.msg}` : e.msg
        }
        try {
          return JSON.stringify(e)
        } catch {
          return String(e)
        }
      })
      .join("; ")
  }
  if (typeof detail === "object" && detail !== null && typeof detail.code === "string") {
    if (detail.code === "plan_limit_reached" || detail.code === "trial_expired") {
      return detail.code
    }
  }
  if (typeof detail === "object" && detail !== null && typeof detail.msg === "string") return detail.msg
  try {
    return JSON.stringify(detail)
  } catch {
    return String(detail)
  }
}

export function apiFetch(path, options = {}, token) {
  return fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  }).then(async (res) => {
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      const d = data.detail
      if (res.status === 403 && d && typeof d === "object" && (d.code === "plan_limit_reached" || d.code === "trial_expired")) {
        window.dispatchEvent(new CustomEvent("aptia-plan-limit", { detail: d }))
        throw new PlanLimitError(d)
      }
      const msg = formatApiErrorDetail(d)
      if (msg === "Error" && res.status >= 500) {
        throw new Error("El servidor no está disponible. Revisá que el backend esté corriendo e intentá de nuevo.")
      }
      if (msg === "Error" && res.status === 401) {
        throw new Error("Email o contraseña incorrectos.")
      }
      throw new Error(msg)
    }
    return data
  })
}
