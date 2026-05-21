# Plan de mejoras UI/UX — Acid Talent OS

**Foco:** UX de formularios + pulido visual y consistencia
**Restricción:** mantener estilo actual (dark glassmorphism, cyan→blue→purple, radius 14/22/999, blur 24, Inter)
**Stack:** React + CSS plano (sin Tailwind)

---

## Resumen del estado actual

| Dimensión | Hoy | Veredicto |
|---|---|---|
| Sistema de color | Tokenizado en `:root` con dark + light | Sólido, no hace falta tocar |
| Espaciado | Mezcla de 10/12/14/16/18/20/22/24/28 | Inconsistente, necesita escala 4/8 |
| Border radius | 12/14/18/20/22/24/28/30/32 | Demasiada variación |
| Tipografía | Inter, jerarquía grande/clara | Bien |
| Glassmorphism | Aplicado coherente en cards/topbar/sidebar | Bien |
| Forms | Sin labels asociados, sin validación inline, sin helper text, sin success states | Necesita trabajo |
| Feedback | `window.confirm`, mensajes mezclados error/éxito, sin toasts auto-dismiss, sin skeletons | Necesita trabajo |
| Accesibilidad | Inputs con focus visible; botones e iconos no | Mejora obligada |

---

## Issues detectados, priorizados

### Nivel 1 — Quick wins (alto impacto, bajo esfuerzo)

1. **Tokenizar escala de spacing y radius** (`--space-1` a `--space-8`, `--radius-sm/md/lg/xl`) para futura consistencia. Mantiene los valores actuales como base.
2. **Asociar labels a inputs** con `htmlFor`/`id` en Login, CreateSearch, AdminPanel y CalendarView.
3. **Agregar `autocomplete` y `inputmode`** correctos (email, current-password, new-password) en formularios sensibles.
4. **Indicador de campo requerido** (`*` rojo + `aria-required`) en formularios.
5. **Helper text persistente** debajo de inputs complejos (ej. "Mínimo 8 caracteres" en password admin).
6. **Distinguir error vs éxito** en mensajes (clase `.feedback-success` verde + `.feedback-error` rojo, ambos con ícono).
7. **Toast auto-dismiss** real, fuera del flujo del documento, con cierre manual + `aria-live="polite"`.
8. **File input estilado** que herede del tema (botón "Subir" con extensión y tamaño max visible).
9. **Focus ring global** para `button, a, [role="button"]` con `:focus-visible`.
10. **`aria-label` en botones de ícono** (`×` modal, refresh, theme toggle, notification pill).
11. **Reemplazar `window.confirm`** por un modal de confirmación reutilizable (`ConfirmDialog`) que use el mismo lenguaje visual.
12. **Empty states accionables** con CTA opcional (ej. "Sin notificaciones" + botón "Ver actividad reciente").

### Nivel 2 — Mejoras medias (alto impacto, esfuerzo medio)

13. **Skeleton loaders** para entity-list, candidate-list y kpi-grid mientras carga.
14. **Inline validation on blur**, no on keystroke. Mensaje específico debajo del campo.
15. **Botones con icono + label** consistente. Topbar: ícono refresh (SVG), ícono sol/luna para tema.
16. **Notification pill con icono de campana** y badge numérico encima; estado "0" en gris en lugar de amarillo siempre.
17. **Password strength meter** + show/hide toggle en login y admin (creación).
18. **Multi-step form mejorado** en CreateSearch: progreso visual (3 pasos), pueden avanzar/retroceder.
19. **CTA primario único por vista** (ya casi se cumple, validar caso CreateSearch que tiene 2 botones primarios).
20. **Spacing scale**: aplicar `--space-*` a `.panel`, `.entity-row`, `.card-grid`, `.form-grid`.
21. **Loading state en lista** (no solo en botón): el contenedor muestra shimmer.
22. **Inline edit del CV viewer**: tabs claros para HTML/PDF en vez de switch oculto.

### Nivel 3 — Refactor de patrones (alto valor, mayor esfuerzo)

23. **`<Field>` reutilizable**: label + input + helper + error en un solo componente. Reemplaza el patrón disperso.
24. **`<Toast>` y `<ConfirmDialog>` con context provider** global. Cualquier componente puede disparar feedback sin pasar props.
25. **Tabla de candidatos**: pasar de `entity-row` con flex a una tabla semántica con `<table>` y `aria-sort` (mejora accesibilidad y escaneabilidad).
26. **Calendario mensual** como vista alternativa al semanal (toggle en toolbar).
27. **Dark/Light toggle con preferencia del sistema** (`prefers-color-scheme`) cuando no hay valor en `localStorage`.
28. **Modo compacto/cómodo** (densidad de filas) configurable por usuario en Perfil.

---

## Diseño visual de los cambios

Los cambios mantienen 100% la paleta y el glassmorphism. Los valores nuevos:

```css
/* Spacing scale (mantiene mayoría de valores actuales, ahora tokenizada) */
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-7: 32px;
--space-8: 40px;

/* Radius scale */
--radius-sm: 10px;
--radius-md: 14px;
--radius-lg: 18px;
--radius-xl: 22px;   /* alias de --radius existente */
--radius-2xl: 28px;
--pill: 999px;

/* Feedback colors (ya existen, ahora con variantes "soft" para fondos) */
--success-soft: rgba(88, 214, 141, 0.12);
--warn-soft: rgba(248, 193, 74, 0.12);
--danger-soft: rgba(255, 101, 119, 0.12);
--info-soft: rgba(68, 215, 255, 0.12);

/* Motion */
--ease-out: cubic-bezier(0.2, 0.8, 0.2, 1);
--dur-fast: 140ms;
--dur-base: 220ms;
--dur-slow: 320ms;
```

### Componentes nuevos sugeridos

| Componente | Reemplaza | Beneficio |
|---|---|---|
| `<Field>` | `<label>` + `<input>` sueltos | Label asociado, helper, error inline, required marker automático |
| `<Toast>` | mensajes `setMessage` mezclados | Auto-dismiss, success/error/info, accesible |
| `<ConfirmDialog>` | `window.confirm` | Visual coherente, anuncia destructivo con color rojo, foco gestionado |
| `<Skeleton>` | "Cargando..." textual | Percepción de velocidad, evita CLS |
| `<Icon name="..." />` | Texto en botones de acción rápida | Botones más limpios, ahorro de espacio |
| `<Badge variant="..." />` | `.badge .ok/.warn/.danger` | Más variantes, soporta icono |

---

## Plan de implementación sugerido

**Fase 1 — Fundaciones (1 PR, sin cambios de UX visibles más allá del polish):**
- Tokens nuevos en `:root`
- Focus ring global, `aria-label` faltantes
- File input estilado
- Asociar labels existentes

**Fase 2 — Componentes base (1 PR):**
- `<Field>`, `<Toast>`, `<ConfirmDialog>`, `<Skeleton>`, `<Icon>`
- Reemplazar `window.confirm` en CandidateRow, AdminPanel, CalendarView

**Fase 3 — Refactor de formularios (1 PR):**
- Login, CreateSearch, AdminPanel, CalendarView usando `<Field>`
- Validación on-blur + helper text + required markers

**Fase 4 — Feedback y empty states (1 PR):**
- Skeletons en listas
- Empty states accionables
- Notification pill con icono

---

## Lo que NO se cambia

- Paleta de colores
- Glassmorphism + backdrop blur
- Layout general (sidebar + workspace)
- Estructura de rutas/roles
- Sistema de gradientes para CTAs
- Tipografía Inter
- Breakpoints (1180 / 820 / 520)

---

> Siguiente paso recomendado: revisar el **mockup visual** que armé para ver los cambios aplicados sobre componentes reales antes de meterme al código. Está en `UX_MOCKUP.html`.
