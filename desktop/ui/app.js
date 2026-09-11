const FRONTEND_URL = "http://localhost:5173";
const BACKEND_URL = "http://localhost:8000";

const translations = {
  en: {
    prototype: "Local desktop prototype", refresh: "Check again", eyebrow: "LOCAL SERVICE STATUS",
    title: "Local operator workspace", intro: "This shell checks only fixed localhost services. It never starts Docker or runs host commands.",
    backendHealth: "Backend", readiness: "Readiness", release: "Release", frontend: "Frontend",
    helpTitle: "Copy-only operator commands", helpBody: "Run these commands yourself from the repository. Copying text never executes it.",
    backendHelpTitle: "Backend is not reachable", backendHelpBody: "Start the Docker services, then check health again. PostgreSQL and Redis remain required local services.",
    readinessHelpTitle: "Backend dependencies are not ready", readinessHelpBody: "The backend answered, but a required dependency is degraded. Use the platform check command for a readable diagnosis.",
    frontendHelpTitle: "Frontend is not reachable", frontendHelpBody: "Run the Vite development server from the frontend directory. The desktop shell never starts it automatically.",
    endpoints: "Local endpoints", frontendUrl: "Frontend URL", backendUrl: "Backend URL", connected: "Local frontend connected",
    showStatus: "Service status", openWorkspace: "Open local workspace", checking: "Checking…", reachable: "Reachable", unreachable: "Unreachable",
    ready: "Ready", degraded: "Degraded", available: "Available", unavailable: "Unavailable", unknown: "Unknown",
    start: "Start platform", stop: "Stop platform", restart: "Restart platform", check: "Check health", openFrontend: "Open frontend",
    frontendCommand: "Run frontend dev", backendCommand: "Run Docker services", copy: "Copy", copied: "Command copied. Nothing was executed.",
    readyMessage: "Backend, dependencies, and frontend are ready.", backendMessage: "Backend is unreachable. Start the local Docker services first.",
    readinessMessage: "Backend is reachable, but required dependencies are degraded.", frontendMessage: "Backend is ready. Start the local Vite frontend to open the workspace.",
    platformHealthy: "Backend ready", platformDegraded: "Service problem detected; returning to status."
  },
  es: {
    prototype: "Prototipo de escritorio local", refresh: "Comprobar de nuevo", eyebrow: "ESTADO DE SERVICIOS LOCALES",
    title: "Espacio de trabajo del operador", intro: "Este shell solo comprueba servicios fijos de localhost. Nunca inicia Docker ni ejecuta comandos del sistema.",
    backendHealth: "Backend", readiness: "Disponibilidad", release: "Versión", frontend: "Frontend",
    helpTitle: "Comandos del operador solo para copiar", helpBody: "Ejecuta estos comandos manualmente desde el repositorio. Copiar texto nunca lo ejecuta.",
    backendHelpTitle: "No se puede acceder al backend", backendHelpBody: "Inicia los servicios Docker y vuelve a comprobar. PostgreSQL y Redis siguen siendo servicios locales requeridos.",
    readinessHelpTitle: "Las dependencias del backend no están listas", readinessHelpBody: "El backend respondió, pero una dependencia requerida está degradada. Usa el comando de comprobación para un diagnóstico legible.",
    frontendHelpTitle: "No se puede acceder al frontend", frontendHelpBody: "Ejecuta el servidor de desarrollo Vite desde el directorio frontend. El shell nunca lo inicia automáticamente.",
    endpoints: "Endpoints locales", frontendUrl: "URL del frontend", backendUrl: "URL del backend", connected: "Frontend local conectado",
    showStatus: "Estado de servicios", openWorkspace: "Abrir espacio local", checking: "Comprobando…", reachable: "Accesible", unreachable: "No accesible",
    ready: "Listo", degraded: "Degradado", available: "Disponible", unavailable: "No disponible", unknown: "Desconocida",
    start: "Iniciar plataforma", stop: "Detener plataforma", restart: "Reiniciar plataforma", check: "Comprobar salud", openFrontend: "Abrir frontend",
    frontendCommand: "Ejecutar frontend dev", backendCommand: "Ejecutar servicios Docker", copy: "Copiar", copied: "Comando copiado. No se ejecutó nada.",
    readyMessage: "El backend, sus dependencias y el frontend están listos.", backendMessage: "El backend no está accesible. Inicia primero los servicios Docker locales.",
    readinessMessage: "El backend está accesible, pero hay dependencias requeridas degradadas.", frontendMessage: "El backend está listo. Inicia el frontend Vite local para abrir el espacio.",
    platformHealthy: "Backend listo", platformDegraded: "Se detectó un problema; regresando al estado."
  }
};

const commands = [
  ["start", ".\\scripts\\local\\start_platform.ps1"],
  ["stop", ".\\scripts\\local\\stop_platform.ps1"],
  ["restart", ".\\scripts\\local\\restart_platform.ps1"],
  ["check", ".\\scripts\\local\\check_platform.ps1"],
  ["openFrontend", ".\\scripts\\local\\open_platform.ps1 -Target frontend"],
  ["frontendCommand", "cd frontend; npm run dev"],
  ["backendCommand", "docker compose up -d postgres redis backend celery-worker"]
];

let language = localStorage.getItem("raventech-desktop-language") === "es" ? "es" : "en";
let checking = false;
let platformOpen = false;
let statusPinned = false;
let previouslyReady = false;

function copy(key) {
  return translations[language][key] ?? translations.en[key] ?? key;
}

function renderLanguage() {
  document.documentElement.lang = language;
  document.querySelectorAll("[data-copy]").forEach((node) => {
    node.textContent = copy(node.dataset.copy);
  });
  document.querySelector("#language").textContent = language === "en" ? "Español" : "English";
  document.querySelector("#frontend-url").textContent = FRONTEND_URL;
  document.querySelector("#backend-url").textContent = BACKEND_URL;
  document.querySelector("#commands").replaceChildren(...commands.map(([label, command]) => {
    const row = document.createElement("div");
    row.className = "command";
    const name = document.createElement("label");
    name.textContent = copy(label);
    const code = document.createElement("code");
    code.textContent = command;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = copy("copy");
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(command);
        document.querySelector("#message").textContent = copy("copied");
      } catch {
        document.querySelector("#message").textContent = command;
      }
    });
    row.append(name, code, button);
    return row;
  }));
}

function paint(id, state, detail = "") {
  const node = document.querySelector(id);
  node.textContent = copy(state);
  node.className = state === "ready" || state === "reachable" || state === "available" ? "ok" : state === "checking" ? "" : "offline";
  const detailNode = document.querySelector(id.replace("-status", "-detail"));
  if (detailNode) detailNode.textContent = detail;
}

function showPlatform() {
  statusPinned = false;
  platformOpen = true;
  document.querySelector("#status-view").hidden = true;
  document.querySelector(".topbar").hidden = true;
  document.querySelector("#platform-view").hidden = false;
  const frame = document.querySelector("#platform-frame");
  if (frame.src !== `${FRONTEND_URL}/`) frame.src = FRONTEND_URL;
}

function showStatus(pin = true) {
  statusPinned = pin;
  platformOpen = false;
  document.querySelector("#platform-view").hidden = true;
  document.querySelector(".topbar").hidden = false;
  document.querySelector("#status-view").hidden = false;
}

function setGuidance(name) {
  ["backend", "readiness", "frontend"].forEach((item) => {
    document.querySelector(`#${item}-guidance`).hidden = item !== name;
  });
}

function renderSnapshot(snapshot) {
  const backendState = !snapshot.backend.reachable ? "unreachable" : snapshot.backend.healthy ? "reachable" : "degraded";
  const readinessState = !snapshot.readiness.reachable ? "unreachable" : snapshot.readiness.healthy ? "ready" : "degraded";
  const frontendState = !snapshot.frontend.reachable ? "unreachable" : snapshot.frontend.healthy ? "reachable" : "degraded";

  paint("#backend-status", backendState, snapshot.backend.status ?? "");
  paint("#ready-status", readinessState, snapshot.readiness.status ?? "");
  const releaseStatus = document.querySelector("#release-status");
  releaseStatus.textContent = snapshot.releaseVersion ?? copy("unavailable");
  releaseStatus.className = snapshot.releaseVersion ? "ok" : "offline";
  document.querySelector("#release-detail").textContent = snapshot.release.httpStatus
    ? `HTTP ${snapshot.release.httpStatus}`
    : copy("unknown");
  paint("#frontend-status", frontendState, snapshot.frontend.httpStatus ? `HTTP ${snapshot.frontend.httpStatus}` : "");

  const allReady = snapshot.backend.healthy && snapshot.readiness.healthy && snapshot.frontend.healthy;
  const summary = document.querySelector("#summary");
  const summaryText = document.querySelector("#summary-text");
  const openButton = document.querySelector("#open-platform");
  openButton.hidden = !allReady;

  if (!snapshot.backend.reachable) {
    summary.className = "summary error";
    summaryText.textContent = copy("backendMessage");
    setGuidance("backend");
  } else if (!snapshot.backend.healthy || !snapshot.readiness.healthy) {
    summary.className = "summary warning";
    summaryText.textContent = copy("readinessMessage");
    setGuidance("readiness");
  } else if (!snapshot.frontend.healthy) {
    summary.className = "summary warning";
    summaryText.textContent = copy("frontendMessage");
    setGuidance("frontend");
  } else {
    summary.className = "summary success";
    summaryText.textContent = copy("readyMessage");
    setGuidance("");
  }

  document.querySelector("#platform-summary").textContent = snapshot.releaseVersion
    ? `${copy("platformHealthy")} · ${snapshot.releaseVersion}`
    : copy("platformHealthy");

  if (allReady && !previouslyReady && !statusPinned) showPlatform();
  if (!allReady && platformOpen) {
    document.querySelector("#message").textContent = copy("platformDegraded");
    showStatus(false);
  }
  previouslyReady = allReady;
}

async function refresh() {
  if (checking) return;
  checking = true;
  ["#backend-status", "#ready-status", "#release-status", "#frontend-status"].forEach((id) => paint(id, "checking"));
  try {
    const snapshot = await window.__TAURI__.core.invoke("probe_local_services");
    renderSnapshot(snapshot);
  } catch {
    renderSnapshot({
      backend: { reachable: false, healthy: false }, readiness: { reachable: false, healthy: false },
      release: { reachable: false, healthy: false }, frontend: { reachable: false, healthy: false }, releaseVersion: null
    });
  } finally {
    checking = false;
  }
}

document.querySelector("#language").addEventListener("click", () => {
  language = language === "en" ? "es" : "en";
  localStorage.setItem("raventech-desktop-language", language);
  renderLanguage();
  refresh();
});
document.querySelector("#refresh").addEventListener("click", refresh);
document.querySelector("#show-status").addEventListener("click", () => showStatus(true));
document.querySelector("#open-platform").addEventListener("click", showPlatform);

renderLanguage();
refresh();
window.setInterval(refresh, 15_000);
