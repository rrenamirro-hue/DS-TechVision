'use strict';
const form = document.getElementById('loginForm');
form.addEventListener('submit', async (event) => {
  event.preventDefault(); const button = document.getElementById('loginButton'); const notice = document.getElementById('loginNotice');
  button.disabled = true; notice.textContent = 'Verificando…';
  try {
    const response = await fetch('/api/auth/login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({username: document.getElementById('username').value, password: document.getElementById('password').value})});
    const data = await response.json(); if (!response.ok) throw new Error(data.detail || 'No se pudo iniciar sesión'); window.location.replace('/');
  } catch (error) { notice.textContent = error.message; button.disabled = false; }
});
