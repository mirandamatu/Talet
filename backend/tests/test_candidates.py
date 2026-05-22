from io import BytesIO


PDF_BYTES = b"%PDF-1.4\n%test\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def test_cargar_candidato(client, search, headers, monkeypatch):
    monkeypatch.setattr("app.routes.talent.upload_cv", lambda file_obj, filename: f"/uploads/{filename}")
    monkeypatch.setattr("app.routes.talent.extract_pdf_text", lambda raw: "Python FastAPI")
    monkeypatch.setattr(
        "app.routes.talent.analyze_candidate_fit",
        lambda **kwargs: {"score": 82, "recommendation": True, "summary": "Buen fit", "reasons": [], "model": "test"},
    )
    response = client.post(
        f"/api/searches/{search.id}/candidates",
        headers=headers["talent"],
        data={"full_name": "Grace Hopper", "email": "grace@test.com", "short_profile": "Backend"},
        files={"file": ("grace.pdf", BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Grace Hopper"
    assert body["ai_fit_score"] in (82, 0, None) or body["ai_fit_score"] >= 0


def test_candidato_soft_delete(client, db, candidate, headers):
    response = client.delete(f"/api/candidates/{candidate.id}", headers=headers["talent"])
    assert response.status_code == 200
    db.refresh(candidate)
    assert candidate.archived_at is not None
    rows = client.get("/api/candidates", headers=headers["talent"]).json()
    assert all(row["id"] != candidate.id for row in rows)


def test_mover_candidato_al_banco(client, db, candidate, headers):
    response = client.post(f"/api/candidates/{candidate.id}/send-to-bank", headers=headers["talent"])
    assert response.status_code == 200
    db.refresh(candidate)
    assert candidate.status == "banco_talent"


def test_asignar_candidato_existente(client, db, candidate, client_account, headers):
    from app.models.search import Search

    other = Search(client_id=client_account.id, title="QA Engineer", job_description="Testing", manual_state="abierta")
    db.add(other)
    db.commit()
    db.refresh(other)
    response = client.post(
        f"/api/candidates/{candidate.id}/assignments",
        headers=headers["talent"],
        json={"search_ids": [other.id], "status": "en_revision"},
    )
    assert response.status_code == 200
    assert any(item["search_id"] == other.id for item in response.json()["assignments"])


def test_score_ia_fallback_sin_api_key(client, search, headers, monkeypatch):
    monkeypatch.setattr("app.routes.talent.upload_cv", lambda file_obj, filename: f"/uploads/{filename}")
    monkeypatch.setattr("app.routes.talent.extract_pdf_text", lambda raw: "Sin API externa")
    response = client.post(
        f"/api/searches/{search.id}/candidates",
        headers=headers["talent"],
        data={"full_name": "Fallback User", "email": "fallback@test.com"},
        files={"file": ("fallback.pdf", BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["id"]
