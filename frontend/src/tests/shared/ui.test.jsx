import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { expect, test, vi } from "vitest"

import { ConfirmProvider, Field, FileInput, PasswordInput, Skeleton, ToastProvider, useConfirm, useToast } from "../../shared/ui.jsx"

test("Field renderiza label, helper y error", () => {
  render(
    <Field label="Email" helper="Usá tu correo" error="Email inválido">
      <input />
    </Field>
  )
  expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
  expect(screen.getByText(/email inválido/i)).toBeInTheDocument()
})

test("Toast aparece al invocar success", () => {
  function Trigger() {
    const toast = useToast()
    return <button type="button" onClick={() => toast.success("Guardado", "Todo listo")}>Mostrar</button>
  }
  render(
    <ToastProvider>
      <Trigger />
    </ToastProvider>
  )
  fireEvent.click(screen.getByRole("button", { name: /mostrar/i }))
  expect(screen.getByText(/guardado/i)).toBeInTheDocument()
  expect(screen.getByText(/todo listo/i)).toBeInTheDocument()
})

test("ConfirmDialog ejecuta onConfirm y onCancel", async () => {
  const confirmed = vi.fn()
  function Trigger() {
    const confirm = useConfirm()
    return (
      <button
        type="button"
        onClick={async () => {
          if (await confirm({ title: "Confirmar acción", confirmLabel: "Aceptar" })) confirmed()
        }}
      >
        Abrir
      </button>
    )
  }
  render(
    <ConfirmProvider>
      <Trigger />
    </ConfirmProvider>
  )
  fireEvent.click(screen.getByRole("button", { name: /abrir/i }))
  fireEvent.click(screen.getByRole("button", { name: /aceptar/i }))
  await waitFor(() => expect(confirmed).toHaveBeenCalledTimes(1))

  fireEvent.click(screen.getByRole("button", { name: /abrir/i }))
  fireEvent.click(screen.getByRole("button", { name: /cancelar/i }))
  expect(confirmed).toHaveBeenCalledTimes(1)
})

test("Skeleton se renderiza con ancho y alto", () => {
  render(<Skeleton width={120} height={24} />)
  const skeleton = document.querySelector(".skeleton")
  expect(skeleton).toHaveStyle({ width: "120px", height: "24px" })
})

test("PasswordInput alterna show/hide", () => {
  render(<PasswordInput value="secret" onChange={() => {}} />)
  const input = screen.getByDisplayValue("secret")
  expect(input).toHaveAttribute("type", "password")
  fireEvent.click(screen.getByRole("button", { name: /mostrar contraseña/i }))
  expect(input).toHaveAttribute("type", "text")
})

test("FileInput notifica el archivo seleccionado y permite limpiar", () => {
  const onChange = vi.fn()
  render(<FileInput value={null} onChange={onChange} accept="application/pdf" />)
  const input = document.querySelector("input[type='file']")
  const file = new File(["pdf"], "cv.pdf", { type: "application/pdf" })
  fireEvent.change(input, { target: { files: [file] } })
  expect(onChange).toHaveBeenCalledWith(file)
})
