import { EmptyState, Icon } from "../../shared/ui.jsx"

export function Notifications({ items, onReadAll, onMarkRead, onArchive }) {
  const unread = items.filter((item) => item.status === "unread").length
  return (
    <div className="view-stack">
      <div className="pill-row" style={{ justifyContent: "space-between" }}>
        <span className="badge">
          <Icon name="bell" size={12} />
          {unread > 0 ? `${unread} sin leer` : "Todo al día"}
        </span>
        {unread > 0 && (
          <button type="button" className="ghost-action" onClick={onReadAll}>
            <Icon name="check" size={14} />
            Marcar todas como leídas
          </button>
        )}
      </div>
      {items.length === 0 ? (
        <EmptyState
          icon="bell"
          title="Sin notificaciones pendientes"
          description="Cuando un candidato avance o se programe una entrevista vas a verlo acá."
        />
      ) : (
        <section className="entity-list">
          {items.map((item) => (
            <article key={item.id} className="entity-row">
              <div>
                <strong>{item.title || "Notificación"}</strong>
                <span>{item.message || ""}</span>
              </div>
              <div className="row-actions">
                <span className={item.status === "unread" ? "badge warn" : "badge"}>
                  <Icon name={item.status === "unread" ? "clock" : "check"} size={12} />
                  {item.status === "unread" ? "Sin leer" : "Leída"}
                </span>
                {item.status === "unread" && (
                  <button type="button" className="ghost-action" onClick={() => onMarkRead?.(item.id)}>
                    Marcar leída
                  </button>
                )}
                <button type="button" className="icon-action mini" onClick={() => onArchive([item.id])} aria-label="Archivar notificación" title="Archivar">
                  <Icon name="trash" size={14} />
                </button>
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  )
}
