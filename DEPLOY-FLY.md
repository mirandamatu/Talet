# Deploy en Fly.io (Acid Talent)

Dos apps en la misma organización de Fly:

| App | Rol | URL |
|-----|-----|-----|
| `acid-talent-api` | FastAPI + Postgres | `https://acid-talent-api.fly.dev` |
| `acid-talent-web` | React (nginx) | `https://acid-talent-web.fly.dev` |

Región por defecto: `gru` (São Paulo).

## 1. Base de datos

```powershell
fly postgres create --name acid-talent-db --region gru --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 3
fly postgres attach acid-talent-db --app acid-talent-api
```

`attach` define el secreto `DATABASE_URL` en la app del API.

## 2. Backend

```powershell
cd backend
fly apps create acid-talent-api
fly secrets set JWT_SECRET="tu-secreto-largo-y-aleatorio"
# Opcional: AI_API_KEY, S3_*, SMTP_*, GOOGLE_OAUTH_*
fly volumes create uploads_data --region gru --size 1
fly deploy
```

Tras el primer deploy, las migraciones y el seed corren en el arranque del contenedor.

## 3. Frontend

```powershell
cd frontend
fly apps create acid-talent-web
fly deploy
```

El frontend envía `/api` y `/uploads` al API público (`https://acid-talent-api.fly.dev`) para que Fly pueda despertar la máquina del backend cuando está en auto-stop.

## 4. Google OAuth (correo y calendario)

Sin estos secretos en Fly, Perfil muestra *«Google no disponible todavía»* aunque funcione en local.

### Fly

```powershell
fly secrets set GOOGLE_OAUTH_CLIENT_ID="tu-client-id" GOOGLE_OAUTH_CLIENT_SECRET="tu-secret" GOOGLE_OAUTH_REDIRECT_URI="https://acid-talent-api.fly.dev/api/recruiting/google-calendar/callback" --app acid-talent-api
```

### Google Cloud Console

1. APIs habilitadas: **Google Calendar API** y **Gmail API**.
2. Cliente OAuth tipo **Aplicación web**.
3. **URIs de redirección autorizados** (ambas si usás local y prod):
   - `http://localhost:8000/api/recruiting/google-calendar/callback`
   - `https://acid-talent-api.fly.dev/api/recruiting/google-calendar/callback`
4. Pantalla de consentimiento en **Prueba (Testing)**:
   - Solo pueden conectar cuentas listadas en **Usuarios de prueba**.
   - Agregá el Gmail con el que vas a probar (p. ej. el de `comercial@acidt.com` si es Gmail, o tu cuenta personal).
5. Al conectar puede aparecer *«Google no verificó esta app»* → **Avanzado** → **Ir a Atipia (no seguro)** (normal en modo prueba).

Si falla con `access_denied` o no aparece tu cuenta, casi siempre falta agregar ese Gmail como usuario de prueba.

## Usuarios demo (seed)

- `admin@acidt.com` / `admin123`
- `comercial@acidt.com` / `comercial123`
- `talent@acidt.com` / `talent123`
- `cliente@acidt.com` / `cliente123`

## Comandos útiles

```powershell
fly logs --app acid-talent-api
fly logs --app acid-talent-web
fly ssh console --app acid-talent-api
```
