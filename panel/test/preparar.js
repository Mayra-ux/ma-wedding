// Preparación de jsdom para las pruebas de interfaz (las de entorno node no tienen window).
globalThis.IS_REACT_ACT_ENVIRONMENT = true

if (typeof window !== 'undefined') {
  // jsdom no implementa <dialog> modal: lo justo para abrir, cerrar y emitir `close`.
  if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.showModal) {
    HTMLDialogElement.prototype.showModal = function showModal() {
      this.setAttribute('open', '')
    }
    HTMLDialogElement.prototype.close = function close() {
      if (!this.hasAttribute('open')) return
      this.removeAttribute('open')
      this.dispatchEvent(new Event('close'))
    }
  }

  // Pantalla angosta por defecto (celular); las pruebas pueden cambiarlo.
  globalThis.__anchoPantalla = false
  window.matchMedia = (consulta) => ({
    matches: globalThis.__anchoPantalla,
    media: consulta,
    addEventListener() {},
    removeEventListener() {},
  })

  window.scrollTo = () => {}
}
