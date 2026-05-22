import { useState } from "react"

import BrandMark from "../../BrandMark.jsx"
import { apiFetch } from "../../shared/api"
import { Feedback, Field, Icon, PasswordInput } from "../../shared/ui.jsx"

export function Login({ onLogin }) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [emailError, setEmailError] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  function validateEmail(value) {
    if (!value.trim()) return "Ingresá tu email."
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return "Formato de email inválido."
    return ""
  }

  async function submit(event) {
    event.preventDefault()
    const ee = validateEmail(email)
    setEmailError(ee)
    if (ee) return
    setError("")
    setLoading(true)
    try {
      const data = await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      })
      onLogin(data.access_token, data.user)
    } catch (err) {
      const msg = err.message === "ACCOUNT_INACTIVE"
        ? "Cuenta desactivada. Contactá al administrador."
        : err.message || "No se pudo iniciar sesión."
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-screen">
      <section className="login-panel">
        <BrandMark />
        <p className="eyebrow">Atipia OS</p>
        <h1>Recruiting inteligente para equipos modernos.</h1>
        <p className="login-copy">
          Seguimiento de búsquedas, candidatos, IA de fit y feedback en una interfaz nueva.
        </p>
      </section>
      <form className="login-card" onSubmit={submit} noValidate>
        <h2>Ingresar</h2>
        <Field
          label="Email"
          required
          error={emailError}
          helper="Usá el mismo email que te envió Atipia."
        >
          <input
            type="email"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value)
              if (emailError) setEmailError("")
            }}
            onBlur={(event) => setEmailError(validateEmail(event.target.value))}
            autoComplete="email"
            inputMode="email"
            placeholder="tu@email.com"
            autoFocus
            required
          />
        </Field>
        <Field label="Contraseña" required>
          <PasswordInput
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Tu contraseña"
            autoComplete="current-password"
            required
          />
        </Field>
        {error && <Feedback variant="error" title="No se pudo iniciar sesión">{error}</Feedback>}
        <button
          className="primary-action"
          type="submit"
          disabled={loading}
          data-busy={loading || undefined}
        >
          {loading ? "Ingresando..." : (<>Entrar al portal <Icon name="arrowRight" size={16} /></>)}
        </button>
      </form>
    </div>
  )
}
