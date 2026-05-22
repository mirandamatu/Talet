def test_crear_busqueda(client, client_account, headers):
    response = client.post(
        f"/api/clients/{client_account.id}/searches",
        headers=headers["comercial"],
        json={"client_id": client_account.id, "title": "Data Engineer", "job_description": "SQL y Python"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"]
    assert body["title"] == "Data Engineer"
    assert body["client_id"] == client_account.id


def test_listar_busquedas(client, search, headers):
    response = client.get("/api/searches", headers=headers["talent"])
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert {"id", "title", "client_id"}.issubset(rows[0])


def test_cliente_solo_ve_sus_busquedas(client, search, headers):
    response = client.get("/api/my/searches", headers=headers["cliente"])
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [search.id]


def test_archivar_busqueda(client, db, search, headers):
    response = client.delete(f"/api/searches/{search.id}", headers=headers["comercial"])
    assert response.status_code == 200
    db.refresh(search)
    assert search.archived_at is not None
    assert client.get("/api/searches", headers=headers["talent"]).json() == []


def test_actualizar_estado_busqueda(client, db, search, headers):
    response = client.patch(
        f"/api/searches/{search.id}",
        headers=headers["comercial"],
        json={"manual_state": "activa"},
    )
    assert response.status_code == 200
    db.refresh(search)
    assert search.manual_state == "activa"
