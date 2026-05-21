import { getGoogleCalendarConnectUrl } from "./calendar"

export const GOOGLE_OAUTH_MESSAGE = "atipia-google-oauth"

const POPUP_FEATURES = "width=520,height=720,menubar=no,toolbar=no,location=yes,status=no,scrollbars=yes,resizable=yes"

/**
 * Abre el consentimiento de Google en popup y espera postMessage del callback del backend.
 */
export function connectGoogleWithPopup(token) {
  return getGoogleCalendarConnectUrl(token).then(({ url }) => {
    if (!url) {
      return Promise.reject(new Error("No se pudo iniciar la conexión con Google."))
    }

    return new Promise((resolve, reject) => {
      const popup = window.open(url, "atipia-google-oauth", POPUP_FEATURES)
      if (!popup) {
        reject(new Error("Tu navegador bloqueó la ventana emergente. Permitila para este sitio e intentá de nuevo."))
        return
      }

      let settled = false
      const timeoutMs = 5 * 60 * 1000

      const finish = (fn, value) => {
        if (settled) return
        settled = true
        cleanup()
        fn(value)
      }

      const timer = window.setTimeout(() => {
        finish(reject, new Error("La conexión tardó demasiado. Cerrá la ventana de Google e intentá de nuevo."))
      }, timeoutMs)

      const poll = window.setInterval(() => {
        if (popup.closed && !settled) {
          finish(reject, new Error("Cerraste la ventana antes de terminar. Volvé a intentar si querés conectar Google."))
        }
      }, 500)

      function onMessage(event) {
        const data = event.data
        if (!data || data.type !== GOOGLE_OAUTH_MESSAGE) return
        if (data.status === "success") {
          finish(resolve, { status: "success" })
        } else {
          finish(reject, new Error(data.message || "No se pudo conectar con Google."))
        }
      }

      function cleanup() {
        window.clearTimeout(timer)
        window.clearInterval(poll)
        window.removeEventListener("message", onMessage)
      }

      window.addEventListener("message", onMessage)
      popup.focus()
    })
  })
}
