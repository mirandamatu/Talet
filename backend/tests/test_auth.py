def test_login_valido(client, users):
    response = client.post("/api/auth/login", json={"email": "talent@test.com", "password": "secret123"})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user"]["role"] == "TALENT"


def test_login_password_incorrecto(client, users):
    response = client.post("/api/auth/login", json={"email": "talent@test.com", "password": "bad"})
    assert response.status_code == 401


def test_login_cuenta_inactiva(client, users):
    response = client.post("/api/auth/login", json={"email": "inactive@test.com", "password": "secret123"})
    assert response.status_code == 401
    assert response.json()["detail"] == "ACCOUNT_INACTIVE"


def test_token_requerido_en_endpoint_protegido(client):
    response = client.get("/api/searches")
    assert response.status_code == 401


def test_rol_incorrecto_bloqueado(client, headers):
    response = client.get("/api/admin/users", headers=headers["cliente"])
    assert response.status_code == 403
