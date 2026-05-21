import { apiFetch } from "../../shared/api"

export async function getGoogleCalendarStatus(token) {
  return apiFetch("/recruiting/google-calendar/status", {}, token)
}

export async function getGoogleCalendarConnectUrl(token) {
  return apiFetch("/recruiting/google-calendar/connect", {}, token)
}

export async function disconnectGoogleCalendar(token) {
  return apiFetch("/recruiting/google-calendar/disconnect", { method: "POST" }, token)
}

export async function createInterviewProposal(payload, token) {
  return apiFetch("/recruiting/interviews/proposals", { method: "POST", body: JSON.stringify(payload) }, token)
}
