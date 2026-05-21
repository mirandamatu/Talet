import { apiFetch } from "../../shared/api"

export async function generateMailDraft(payload, token) {
  return apiFetch("/recruiting/mail/draft", { method: "POST", body: JSON.stringify(payload) }, token)
}

export async function sendMailDraft(payload, token) {
  return apiFetch("/recruiting/mail/send", { method: "POST", body: JSON.stringify(payload) }, token)
}
