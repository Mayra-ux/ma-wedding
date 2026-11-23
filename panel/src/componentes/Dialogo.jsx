// Diálogo de confirmación con <dialog> nativo: modal (atrapa el foco), cierra con Esc y
// devuelve el foco al botón que lo abrió.
import { useEffect, useId, useRef } from 'react'

export default function Dialogo({ abierto, titulo, children, confirmar, alConfirmar, alCerrar, ocupado }) {
  const ref = useRef(null)
  const previo = useRef(null)
  const idTitulo = useId()

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (abierto && !d.open) {
      previo.current = document.activeElement
      d.showModal()
    } else if (!abierto && d.open) {
      d.close()
    }
  }, [abierto])

  useEffect(() => {
    const d = ref.current
    if (!d) return
    const cerrado = () => {
      const p = previo.current
      if (p && typeof p.focus === 'function' && document.contains(p)) p.focus()
      if (abierto) alCerrar()
    }
    d.addEventListener('close', cerrado)
    return () => d.removeEventListener('close', cerrado)
  }, [abierto, alCerrar])

  return (
    <dialog ref={ref} className="dialogo" aria-labelledby={idTitulo}>
      <h2 id={idTitulo}>{titulo}</h2>
      <div className="dialogo-cuerpo">{children}</div>
      <div className="acciones">
        <button type="button" className="boton secundario" onClick={() => ref.current?.close()} disabled={ocupado}>
          Cancelar
        </button>
        <button type="button" className="boton" onClick={alConfirmar} disabled={ocupado}>
          {confirmar}
        </button>
      </div>
    </dialog>
  )
}
