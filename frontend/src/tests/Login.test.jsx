import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

import { Login } from "../features/auth/Login.jsx"

const originalFetch = global.fetch

beforeEach(() => {
  global.fetch = vi.fn()
})

afterEach(() => {
  global.fetch = originalFetch
  vi.restoreAllMocks()
})

test("muestra error si el email está vacío", async () => {
  render(<Login onLogin={() => {}} />)
  fireEvent.click(screen.getByRole("button", { name: /entrar/i }))
  expect(await screen.findByText(/ingresá tu email/i)).toBeInTheDocument()
})

test("muestra error si el email es inválido", async () => {
  render(<Login onLogin={() => {}} />)
  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "noemail" } })
  fireEvent.blur(screen.getByLabelText(/email/i))
  expect(await screen.findByText(/formato de email inválido/i)).toBeInTheDocument()
})

test("muestra estado de carga al hacer submit", async () => {
  global.fetch.mockReturnValue(new Promise(() => {}))
  render(<Login onLogin={() => {}} />)
  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "test@test.com" } })
  fireEvent.change(screen.getByPlaceholderText(/tu contraseña/i), { target: { value: "123456" } })
  fireEvent.click(screen.getByRole("button", { name: /entrar/i }))
  expect(await screen.findByText(/ingresando/i)).toBeInTheDocument()
})

test("llama onLogin cuando las credenciales son válidas", async () => {
  const onLogin = vi.fn()
  global.fetch.mockResolvedValue({
    ok: true,
    json: async () => ({ access_token: "token", user: { id: 1, role: "TALENT" } })
  })
  render(<Login onLogin={onLogin} />)
  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "test@test.com" } })
  fireEvent.change(screen.getByPlaceholderText(/tu contraseña/i), { target: { value: "123456" } })
  fireEvent.click(screen.getByRole("button", { name: /entrar/i }))
  await waitFor(() => expect(onLogin).toHaveBeenCalledWith("token", { id: 1, role: "TALENT" }))
})
