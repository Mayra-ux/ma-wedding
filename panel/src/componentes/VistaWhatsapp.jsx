// Vista previa de un mensaje de WhatsApp armado por la API, el enlace para abrirlo y la marca
// de enviado. El texto se muestra como texto. Solo se abre una URL https://wa.me/.
import { urlWhatsappSegura } from '../api.js'
import { telefono } from '../formato.js'

export default function VistaWhatsapp({ mensaje, etiquetaMarcar, alMarcar, ocupado, alCerrar }) {
  const url = urlWhatsappSegura(mensaje.wa_url)
  return (
    <div className="whatsapp">
      <p className="whatsapp-destino">Para: {telefono(mensaje.telefono)}</p>
      <p className="whatsapp-texto" data-testid="texto-whatsapp">
        {mensaje.texto}
      </p>
      <div className="acciones">
        {url ? (
          <a className="boton" href={url} target="_blank" rel="noopener noreferrer">
            Abrir en WhatsApp
          </a>
        ) : null}
        <button type="button" className="boton secundario" onClick={alMarcar} disabled={ocupado}>
          {etiquetaMarcar}
        </button>
        <button type="button" className="boton enlace-boton" onClick={alCerrar}>
          Cerrar
        </button>
      </div>
      <p className="nota">Marca como enviado solo después de enviarlo en WhatsApp.</p>
    </div>
  )
}
