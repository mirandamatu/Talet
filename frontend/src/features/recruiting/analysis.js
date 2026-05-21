import { apiFetch } from "../../shared/api"

export async function analyzeCandidatesForSearch(searchId, token) {
  return apiFetch(`/recruiting/searches/${searchId}/ai/analyze-candidates`, { method: "POST" }, token)
}

export async function matchCandidatesForSearch(searchId, token) {
  return apiFetch(`/recruiting/searches/${searchId}/ai/match-candidates`, { method: "POST" }, token)
}

export async function listCandidateAnalyses(searchId, token) {
  return apiFetch(`/recruiting/searches/${searchId}/ai/candidate-analyses`, {}, token)
}

export async function listCandidateSearchAnalyses(candidateId, token) {
  return apiFetch(`/recruiting/candidates/${candidateId}/search-analyses`, {}, token)
}
