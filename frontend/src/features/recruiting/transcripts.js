import { apiFetch } from "../../shared/api"

export async function saveTranscript(payload, token) {
  return apiFetch("/recruiting/transcripts", { method: "POST", body: JSON.stringify(payload) }, token)
}

export async function uploadTranscript(formData, token) {
  return apiFetch("/recruiting/transcripts/upload", { method: "POST", body: formData }, token)
}

export async function getCandidateCvHtml(candidateId, token) {
  return apiFetch(`/recruiting/candidates/${candidateId}/cv-html`, {}, token)
}
