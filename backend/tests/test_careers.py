from io import BytesIO


PDF_BYTES = b"%PDF-1.4\n%test\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def test_career_page_publica(client, search):
    response = client.get("/api/careers/cliente-test")
    assert response.status_code == 200
    body = response.json()
    assert body["client"]["slug"] == "cliente-test"
    assert body["jobs"][0]["id"] == search.id


def test_postulacion_publica(client, search, monkeypatch):
    monkeypatch.setattr("app.routes.careers.upload_cv", lambda file_obj, filename: f"/uploads/{filename}")
    monkeypatch.setattr("app.routes.careers.extract_pdf_text", lambda raw: "Python")
    monkeypatch.setattr(
        "app.routes.careers.analyze_candidate_fit",
        lambda **kwargs: {"score": 70, "recommendation": True, "summary": "OK", "reasons": [], "model": "mock"},
    )
    response = client.post(
        "/api/careers/cliente-test/apply",
        data={
            "search_id": str(search.id),
            "full_name": "Public Candidate",
            "email": "public@test.com",
            "personal_description": "Me interesa el rol",
        },
        files={"cv": ("public.pdf", BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_slug_inexistente_devuelve_404(client):
    response = client.get("/api/careers/slug-que-no-existe")
    assert response.status_code == 404
