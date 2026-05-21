import { apiFetch } from "../../shared/api"

export async function listConversations(token) {
  return apiFetch("/hub/conversations", {}, token)
}

export async function createConversation(payload, token) {
  return apiFetch("/hub/conversations", { method: "POST", body: JSON.stringify(payload) }, token)
}

export async function listMessages(conversationId, token) {
  return apiFetch(`/hub/conversations/${conversationId}/messages`, {}, token)
}

export async function sendMessage(conversationId, body, token) {
  return apiFetch(`/hub/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ body }),
  }, token)
}

export async function summarizeConversation(conversationId, token) {
  return apiFetch(`/hub/conversations/${conversationId}/summarize`, { method: "POST" }, token)
}

export async function listSummaries(conversationId, token) {
  return apiFetch(`/hub/conversations/${conversationId}/summaries`, {}, token)
}
