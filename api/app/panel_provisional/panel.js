// Página provisional del panel (I-6). Todo texto de la API se inserta con textContent.
(function () {
  'use strict';
  var ROLES = { admin: 'Novios (acceso total)', lector: 'Planner (solo lectura y exportación)' };
  var csrf = null;

  function $(id) { return document.getElementById(id); }

  function mostrar(id) {
    ['cargando', 'sin-sesion', 'con-sesion'].forEach(function (s) { $(s).hidden = s !== id; });
  }

  function error(texto) {
    var e = $('error');
    e.textContent = texto;
    e.hidden = !texto;
  }

  function cargar() {
    error('');
    fetch('/api/v1/auth/me', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) {
        if (r.status === 401) { mostrar('sin-sesion'); return null; }
        if (!r.ok) { throw new Error('estado ' + r.status); }
        return r.json();
      })
      .then(function (datos) {
        if (!datos) { return; }
        csrf = datos.csrf_token;
        $('correo').textContent = datos.correo;
        $('rol').textContent = ROLES[datos.rol] || datos.rol;
        mostrar('con-sesion');
      })
      .catch(function () {
        mostrar('sin-sesion');
        error('No se pudo comprobar la sesión. Revisa que la API esté encendida y recarga.');
      });
  }

  function salir() {
    var boton = $('salir');
    boton.disabled = true;
    fetch('/api/v1/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRF-Token': csrf || '' }
    })
      .then(function (r) {
        if (r.status !== 204 && r.status !== 401) { throw new Error('estado ' + r.status); }
        csrf = null;
        mostrar('sin-sesion');
      })
      .catch(function () { error('No se pudo cerrar la sesión. Inténtalo de nuevo.'); })
      .then(function () { boton.disabled = false; });
  }

  document.addEventListener('DOMContentLoaded', function () {
    $('salir').addEventListener('click', salir);
    cargar();
  });
})();
