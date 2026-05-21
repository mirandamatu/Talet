/** Logo Atipia (PNG con icono verde sobre fondo crema). */
export default function BrandMark({ small }) {
  return (
    <div
      className={
        small ? "brand-mark small brand-mark--asset" : "brand-mark brand-mark--asset"
      }
      aria-hidden="true"
    >
      <img
        className="brand-mark-img"
        src="/atipia-logo.png"
        alt=""
        width={small ? 44 : 64}
        height={small ? 44 : 64}
        decoding="async"
      />
    </div>
  )
}
