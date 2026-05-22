def test_reanalizar_candidato_con_mock(client, candidate, headers, monkeypatch):
    monkeypatch.setattr("app.routes.ai._candidate_cv_text", lambda candidate: "Python")
    monkeypatch.setattr(
        "app.routes.ai.analyze_candidate_fit",
        lambda **kwargs: {"score": 91, "recommendation": True, "summary": "Muy buen fit", "reasons": ["Python"], "model": "mock"},
    )
    response = client.post(f"/api/ai/candidates/{candidate.id}/reanalyze", headers=headers["talent"])
    assert response.status_code == 200
    assert response.json()["score"] == 91


def test_reanalizar_busqueda_con_mock(client, search, headers, monkeypatch):
    monkeypatch.setattr(
        "app.routes.ai.analyze_job_questions",
        lambda **kwargs: {"needs_follow_up": True, "summary": "Faltan datos", "questions": ["¿Budget?"], "model": "mock"},
    )
    response = client.post(f"/api/ai/searches/{search.id}/questions/reanalyze", headers=headers["talent"])
    assert response.status_code == 200
    body = response.json()
    assert body["needs_follow_up"] is True
    assert body["questions"] == ["¿Budget?"]


def test_ai_sin_cv_devuelve_score_cero(client, db, candidate, headers, monkeypatch):
    candidate.cv_file_url = None
    db.commit()
    monkeypatch.setattr(
        "app.routes.ai.analyze_candidate_fit",
        lambda **kwargs: {"score": 0, "recommendation": False, "summary": "Sin CV", "reasons": [], "model": "heuristic"},
    )
    response = client.post(f"/api/ai/candidates/{candidate.id}/reanalyze", headers=headers["talent"])
    assert response.status_code == 200
    assert response.json()["score"] == 0
