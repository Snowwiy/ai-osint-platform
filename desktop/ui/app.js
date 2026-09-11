const FRONTEND_URL = "http://localhost:5173";
const translations = {
  en: {
    prototype: "Local desktop prototype", refresh: "Check again", eyebrow: "LOCAL SERVICE STATUS",
    title: "Preparing the local workspace", intro: "This shell checks only fixed localhost services. It never starts Docker or runs host commands.",
    backendHealth: "Backend health", readiness: "Readiness", release: "Release", frontend: "Frontend",
    helpTitle: "Start the local services", helpBody: "Run these commands yourself from the repository. The buttons copy text only.",
    endpoints: "Local endpoints", frontendUrl: "Frontend URL", backendUrl: "Backend URL", connected: "Local frontend connected",
    showStatus: "Service status", checking: "Checking…", available: "Available", unavailable: "Unavailable", unknown: "Unknown",
    start: "Start", stop: "Stop", restart: "Restart", check: "Check", frontendCommand: "Frontend", copy: "Copy", copied: "Command copied. Nothing was executed.",
    readyMessage: "Services are ready. Opening the existing local web application.",
    unavailableMessage: "One or more local services are unavailable. Use the copyable guidance above."
  },
  es: {
    prototype: "Prototipo de escritorio local", refresh: "Comprobar de nuevo", eyebrow: "ESTADO DE SERVICIOS LOCALES",
    title: "Preparando el espacio local", intro: "Este shell solo comprueba servicios fijos de localhost. Nunca inicia Docker ni ejecuta comandos del sistema.",
    backendHealth: "Salud del backend", readiness: "Disponibilidad", release: "Versión", frontend: "Frontend",
    helpTitle: "Iniciar los servicios locales", helpBody: "Ejecuta estos comandos manualmente desde el repositorio. Los botones solo copian texto.",
    endpoints: "Endpoints locales", frontendUrl: "URL del frontend", backendUrl: "URL del backend", connected: "Frontend local conectado",
    showStatus: "Estado de servicios", checking: "Comprobando…", available: "Disponible", unavailable: "No disponible", unknown: "Desconocida",
    start: "Iniciar", stop: "Detener", restart: "Reiniciar", check: "Comprobar", frontendCommand: "Frontend", copy: "Copiar", copied: "Comando copiado. No se ejecutó nada.",
    readyMessage: "Los servicios están listos. Abriendo la aplicación web local existente.",
    unavailableMessage: "Uno o más servicios locales no están disponibles. Usa la guía copiable anterior."
  }
};
const commands = [
  ["start", ".\\scripts\\local\\start_platform.ps1"],
  ["stop", ".\\scripts\\local\\stop_platform.ps1"],
  ["restart", ".\\scripts\\local\\restart_platform.ps1"],
  ["check", ".\\scripts\\local\\check_platform.ps1"],
  ["frontendCommand", "cd frontend; npm run dev"]
];
let language = localStorage.getItem("raventech-desktop-language") === "es" ? "es" : "en";
let checking = false;

function copy(key) { return translations[language][key] ?? translations.en[key] ?? key; }
function renderLanguage() {
  document.documentElement.lang = language;
  document.querySelectorAll("[data-copy]").forEach((node) => { node.textContent = copy(node.dataset.copy); });
  document.querySelector("#language").textContent = language === "en" ? "Español" : "English";
  document.querySelector("#commands").replaceChildren(...commands.map(([label, command]) => {
    const row = document.createElement("div"); row.className = "command";
    const name = document.createElement("label"); name.textContent = copy(label);
    const code = document.createElement("code"); code.textContent = command;
    const button = document.createElement("button"); button.type = "button"; button.textContent = copy("copy");
    button.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(command); document.querySelector("#message").textContent = copy("copied"); }
      catch { document.querySelector("#message").textContent = command; }
    });
    row.append(name, code, button); return row;
  }));
}
function paint(id, available, text) {
  const node = document.querySelector(id);
  node.textContent = text;
  node.className = available ? "ok" : "offline";
}
function showPlatform() {
  document.querySelector("#status-view").hidden = true;
  document.querySelector(".topbar").hidden = true;
  document.querySelector("#platform-view").hidden = false;
  const frame = document.querySelector("#platform-frame");
  if (frame.src !== FRONTEND_URL + "/") frame.src = FRONTEND_URL;
}
function showStatus() {
  document.querySelector("#platform-view").hidden = true;
  document.querySelector(".topbar").hidden = false;
  document.querySelector("#status-view").hidden = false;
}
async function refresh() {
  if (checking) return;
  checking = true;
  ["#backend-status", "#ready-status", "#release-status", "#frontend-status"].forEach((id) => {
    const node = document.querySelector(id); node.textContent = copy("checking"); node.className = "";
  });
  try {
    const snapshot = await window.__TAURI__.core.invoke("probe_local_services");
    paint("#backend-status", snapshot.backend.available, snapshot.backend.status ?? copy("unavailable"));
    paint("#ready-status", snapshot.readiness.available, snapshot.readiness.status ?? copy("unavailable"));
    paint("#release-status", snapshot.release.available, snapshot.releaseVersion ?? copy("unknown"));
    paint("#frontend-status", snapshot.frontend.available, snapshot.frontend.available ? copy("available") : copy("unavailable"));
    const ready = snapshot.backend.available && snapshot.readiness.available && snapshot.frontend.available;
    document.querySelector("#message").textContent = copy(ready ? "readyMessage" : "unavailableMessage");
    if (ready) window.setTimeout(showPlatform, 650);
    else showStatus();
  } catch {
    document.querySelector("#message").textContent = copy("unavailableMessage");
    showStatus();
  } finally { checking = false; }
}

document.querySelector("#language").addEventListener("click", () => {
  language = language === "en" ? "es" : "en";
  localStorage.setItem("raventech-desktop-language", language);
  renderLanguage(); refresh();
});
document.querySelector("#refresh").addEventListener("click", refresh);
document.querySelector("#show-status").addEventListener("click", showStatus);
renderLanguage();
refresh();
window.setInterval(refresh, 15_000);
