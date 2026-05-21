import { apiFetch } from "../../shared/api"

export async function listCandidateNotes(candidateId, token) {
  return apiFetch(`/recruiting/candidates/${candidateId}/notes`, {}, token)
}

export async function createCandidateNote(candidateId, payload, token) {
  return apiFetch(`/recruiting/candidates/${candidateId}/notes`, { method: "POST", body: JSON.stringify(payload) }, token)
}

export async function updateCandidateNote(candidateId, noteId, payload, token) {
  return apiFetch(`/recruiting/candidates/${candidateId}/notes/${noteId}`, { method: "PATCH", body: JSON.stringify(payload) }, token)
}

export async function deleteCandidateNote(candidateId, noteId, token) {
  return apiFetch(`/recruiting/candidates/${candidateId}/notes/${noteId}`, { method: "DELETE" }, token)
}
