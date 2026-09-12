const FRONTEND_URL = "http://localhost:5173";
const BACKEND_URL = "http://localhost:8000";
const EMBEDDED_FRONTEND_URL = "./app/";

const translations = {
  en: {
    prototype: "RC6 local setup assistant", refresh: "Check again", eyebrow: "LOCAL SERVICE STATUS",
    title: "Local operator workspace", intro: "Validate the project once, then check and control only the approved local services.",
    setupEyebrow: "FIRST-RUN SETUP", setupTitle: "Bind the local RavenTech project", setupBody: "Enter the repository root manually. The desktop validates fixed markers and stores only the validated path.",
    projectPath: "Project path", validateSave: "Validate and save", clearPath: "Clear saved path", resolvedPath: "Resolved project", resolutionSource: "Resolution source", scriptAvailability: "Approved scripts", nextAction: "Next required action",
    wizardProject: "Project", wizardPrerequisites: "Prerequisites", wizardServices: "Local services", stepComplete: "Complete", stepNeedsAction: "Needs action", distributionNote: "Portable and installed builds use this same validated path. Installed builds normally require you to enter it once.",
    pathSaved: "Project path validated and saved.", pathRejected: "That path is not a complete RavenTech repository. Verify the repository root and five approved scripts. Nothing was saved.", enterProjectPath: "Enter the local RavenTech repository root before validating.", pathCleared: "Saved path cleared. Automatic discovery remains available.",
    configured: "Configured", discovered: "Discovered", notConfigured: "Not configured", sourceConfigured: "Saved preference", sourceCurrentDirectory: "Current directory", sourceDevelopmentRelative: "Development-relative", sourceCopyOnly: "Copy-only fallback",
    bindProjectPath: "Enter and save the RavenTech repository root.", correctProjectPath: "Correct the saved project path.", restoreScripts: "Restore the five approved local scripts.", checkRuntime: "Check local runtime prerequisites.",
    startDocker: "Start Docker Desktop, then start the platform.", installDocker: "Install Docker Desktop manually; nothing is installed automatically.", backendPortConflict: "Port 8000 is occupied by another service.", frontendPortConflict: "Port 5173 is occupied by another service.",
    startBackend: "Start the approved local Docker services.", startFrontend: "Start the local Vite frontend for development/browser mode.", fixMigrations: "Use the approved platform start/check flow to resolve pending migrations.", releaseMismatchAction: "The backend release does not match 5.0.0-rc6.", runtimeReady: "Local runtime is ready.",
    backendHealth: "Backend", readiness: "Readiness", release: "Release", frontend: "Frontend", dockerServices: "Docker services", runtimeChecklist: "Runtime checklist", repoStructure: "Repository structure", dockerAvailability: "Docker availability", backendPort: "Port 8000", frontendPort: "Port 5173 (development only)", releaseMatch: "Expected release", migrationState: "Migrations",
    hostMetrics: "Server host metrics", hostNative: "Host native metrics", serverAgentRecommended: "Run ServerHost agent", hostMetricsUnavailable: "Native metrics unavailable; the Monitoring Center will prefer a fresh ServerHost agent and label Docker metrics as fallback.",
    runningDocker: "Running", installedDocker: "Installed, not confirmed running", notDetected: "Not detected", application: "RavenTech responding", occupied: "Occupied by another service", portAvailable: "Available; service not listening", matches: "Matches", mismatch: "Mismatch", pending: "Pending or degraded",
    helpTitle: "Controlled local launcher", helpBody: "Approved actions use five fixed scripts from the validated repository. Copy remains available if runtime execution is unavailable.",
    backendHelpTitle: "Backend is not reachable", backendHelpBody: "Confirm Docker Desktop is running, then use Start platform. PostgreSQL and Redis remain required local services.", readinessHelpTitle: "Backend dependencies are not ready", readinessHelpBody: "A dependency or migration is degraded. Use Check health for a sanitized diagnosis.", frontendHelpTitle: "Frontend is not reachable", frontendHelpBody: "Run the Vite development server from the validated repository. It is not auto-installed or started outside the approved script flow.",
    endpoints: "Local endpoints", frontendUrl: "Frontend source", backendUrl: "Backend URL", firewallTitle: "Windows firewall guidance", firewallBody: "RavenTech uses backend loopback port 8000. Port 5173 is used only for development/browser mode. Do not approve public-network exposure; review any firewall prompt before continuing.", connected: "Frontend workspace", showStatus: "Service status", openWorkspace: "Open local workspace", checking: "Checking…", reachable: "Accessible", unreachable: "Not accessible", ready: "Ready", degraded: "Degraded", embedded: "Embedded", bundledAssets: "Bundled React assets", notRequired: "Not required", available: "Available", unavailable: "Unavailable", unknown: "Unknown",
    start: "Start platform", stop: "Stop platform", restart: "Restart platform", check: "Check health", openFrontend: "Open frontend", frontendCommand: "Run frontend dev", backendCommand: "Run Docker services", copy: "Copy", run: "Run", copied: "Command copied. Nothing was executed.", copyFailed: "Clipboard access is unavailable. Select the visible command text and copy it manually.",
    lastCommand: "Last command", noCommand: "No launcher action has run.", notRun: "Not run", running: "Running approved script…", commandSucceeded: "Approved script completed.", commandFailed: "Approved script failed.", commandUnavailable: "Validated repository script unavailable; use Copy.", commandTimedOut: "Approved script timed out; check status before retrying.",
    confirmTitle: "Confirm local service action", confirmBody: "Run the approved {action} script from the validated project? This changes local service state.", cancel: "Cancel", confirm: "Confirm",
    readyMessage: "Project, backend, dependencies, and frontend are ready.", setupMessage: "Complete first-run project binding to make installed and portable launches reliable.", backendMessage: "Backend is not accessible. Review Docker and port 8000 below.", readinessMessage: "Backend is accessible, but a required dependency or migration needs action.", frontendMessage: "Backend is ready. Start Vite only for development/browser mode.", platformHealthy: "Backend ready", platformDegraded: "Service problem detected; returning to status."
  },
  es: {
    prototype: "Asistente de configuración local RC6", refresh: "Comprobar de nuevo", eyebrow: "ESTADO DE SERVICIOS LOCALES",
    title: "Espacio de trabajo del operador", intro: "Valida el proyecto una vez y después comprueba y controla solo los servicios locales aprobados.",
    setupEyebrow: "CONFIGURACIÓN INICIAL", setupTitle: "Vincular el proyecto local de RavenTech", setupBody: "Introduce manualmente la raíz del repositorio. El escritorio valida marcadores fijos y guarda solo la ruta validada.",
    projectPath: "Ruta del proyecto", validateSave: "Validar y guardar", clearPath: "Borrar ruta guardada", resolvedPath: "Proyecto resuelto", resolutionSource: "Origen de resolución", scriptAvailability: "Scripts aprobados", nextAction: "Siguiente acción requerida",
    wizardProject: "Proyecto", wizardPrerequisites: "Requisitos", wizardServices: "Servicios locales", stepComplete: "Completo", stepNeedsAction: "Requiere acción", distributionNote: "Las versiones portable e instalada usan esta misma ruta validada. La versión instalada normalmente requiere introducirla una vez.",
    pathSaved: "Ruta del proyecto validada y guardada.", pathRejected: "La ruta no es un repositorio completo de RavenTech. Verifica la raíz y los cinco scripts aprobados. No se guardó nada.", enterProjectPath: "Introduce la raíz del repositorio local RavenTech antes de validar.", pathCleared: "Ruta guardada borrada. El descubrimiento automático sigue disponible.",
    configured: "Configurada", discovered: "Detectada", notConfigured: "Sin configurar", sourceConfigured: "Preferencia guardada", sourceCurrentDirectory: "Directorio actual", sourceDevelopmentRelative: "Ruta relativa de desarrollo", sourceCopyOnly: "Alternativa de solo copia",
    bindProjectPath: "Introduce y guarda la raíz del repositorio RavenTech.", correctProjectPath: "Corrige la ruta del proyecto guardada.", restoreScripts: "Restaura los cinco scripts locales aprobados.", checkRuntime: "Comprueba los requisitos del entorno local.",
    startDocker: "Inicia Docker Desktop y después la plataforma.", installDocker: "Instala Docker Desktop manualmente; nada se instala automáticamente.", backendPortConflict: "El puerto 8000 está ocupado por otro servicio.", frontendPortConflict: "El puerto 5173 está ocupado por otro servicio.",
    startBackend: "Inicia los servicios Docker locales aprobados.", startFrontend: "Inicia el frontend Vite solo para desarrollo/modo navegador.", fixMigrations: "Usa el inicio/comprobación aprobado para resolver migraciones pendientes.", releaseMismatchAction: "La versión del backend no coincide con 5.0.0-rc6.", runtimeReady: "El entorno local está listo.",
    backendHealth: "Backend", readiness: "Disponibilidad", release: "Versión", frontend: "Frontend", dockerServices: "Servicios Docker", runtimeChecklist: "Lista del entorno", repoStructure: "Estructura del repositorio", dockerAvailability: "Disponibilidad de Docker", backendPort: "Puerto 8000", frontendPort: "Puerto 5173 (solo desarrollo)", releaseMatch: "Versión esperada", migrationState: "Migraciones",
    hostMetrics: "Métricas del host servidor", hostNative: "Métricas nativas del host", serverAgentRecommended: "Ejecutar agente ServerHost", hostMetricsUnavailable: "Las métricas nativas no están disponibles; el Centro de Monitoreo preferirá un agente ServerHost reciente y etiquetará Docker como alternativa.",
    runningDocker: "En ejecución", installedDocker: "Instalado, ejecución no confirmada", notDetected: "No detectado", application: "RavenTech responde", occupied: "Ocupado por otro servicio", portAvailable: "Disponible; servicio sin escuchar", matches: "Coincide", mismatch: "No coincide", pending: "Pendientes o degradadas",
    helpTitle: "Iniciador local controlado", helpBody: "Las acciones aprobadas usan cinco scripts fijos del repositorio validado. Copiar sigue disponible si la ejecución no está disponible.",
    backendHelpTitle: "No se puede acceder al backend", backendHelpBody: "Confirma que Docker Desktop esté activo y usa Iniciar plataforma. PostgreSQL y Redis siguen siendo necesarios.", readinessHelpTitle: "Las dependencias del backend no están listas", readinessHelpBody: "Una dependencia o migración está degradada. Usa Comprobar salud para un diagnóstico sanitizado.", frontendHelpTitle: "No se puede acceder al frontend", frontendHelpBody: "Ejecuta el servidor Vite desde el repositorio validado. No se instala ni inicia automáticamente fuera del flujo aprobado.",
    endpoints: "Endpoints locales", frontendUrl: "Origen del frontend", backendUrl: "URL del backend", firewallTitle: "Guía del firewall de Windows", firewallBody: "RavenTech usa el puerto local 8000 para el backend. El puerto 5173 solo se usa en desarrollo/modo navegador. No autorices exposición en redes públicas; revisa cualquier aviso del firewall antes de continuar.", connected: "Espacio del frontend", showStatus: "Estado de servicios", openWorkspace: "Abrir espacio local", checking: "Comprobando…", reachable: "Accesible", unreachable: "No accesible", ready: "Listo", degraded: "Degradado", embedded: "Integrado", bundledAssets: "Recursos React incluidos", notRequired: "No requerido", available: "Disponible", unavailable: "No disponible", unknown: "Desconocido",
    start: "Iniciar plataforma", stop: "Detener plataforma", restart: "Reiniciar plataforma", check: "Comprobar salud", openFrontend: "Abrir frontend", frontendCommand: "Ejecutar frontend dev", backendCommand: "Ejecutar servicios Docker", copy: "Copiar", run: "Ejecutar", copied: "Comando copiado. No se ejecutó nada.", copyFailed: "El portapapeles no está disponible. Selecciona el comando visible y cópialo manualmente.",
    lastCommand: "Último comando", noCommand: "No se ha ejecutado ninguna acción.", notRun: "Sin ejecutar", running: "Ejecutando script aprobado…", commandSucceeded: "El script aprobado terminó correctamente.", commandFailed: "El script aprobado falló.", commandUnavailable: "Script del repositorio validado no disponible; usa Copiar.", commandTimedOut: "El script agotó el tiempo; comprueba el estado antes de reintentar.",
    confirmTitle: "Confirmar acción de servicio local", confirmBody: "¿Ejecutar el script aprobado de {action} desde el proyecto validado? Esto cambia el estado del servicio local.", cancel: "Cancelar", confirm: "Confirmar",
    readyMessage: "El proyecto, backend, dependencias y frontend están listos.", setupMessage: "Completa la vinculación inicial para que los inicios instalados y portables sean fiables.", backendMessage: "El backend no está accesible. Revisa Docker y el puerto 8000.", readinessMessage: "El backend responde, pero una dependencia o migración requiere atención.", frontendMessage: "El backend está listo. Inicia Vite solo para desarrollo/modo navegador.", platformHealthy: "Backend listo", platformDegraded: "Se detectó un problema; regresando al estado."
  }
};

const commands = Object.freeze([
  { label: "start", text: ".\\scripts\\local\\start_platform.ps1", invoke: "start_platform", confirm: true },
  { label: "stop", text: ".\\scripts\\local\\stop_platform.ps1", invoke: "stop_platform", confirm: true },
  { label: "restart", text: ".\\scripts\\local\\restart_platform.ps1", invoke: "restart_platform", confirm: true },
  { label: "check", text: ".\\scripts\\local\\check_platform.ps1", invoke: "check_platform", confirm: false },
  { label: "openFrontend", text: ".\\scripts\\local\\open_platform.ps1 -Target frontend", invoke: "open_local_frontend", confirm: false, devOnly: true },
  { label: "frontendCommand", text: "cd frontend; npm run dev", devOnly: true },
  { label: "backendCommand", text: "docker compose up -d postgres redis backend celery-worker" }
]);

let language = localStorage.getItem("raventech-desktop-language") === "es" ? "es" : "en";
let checking = false, platformOpen = false, statusPinned = false, previouslyReady = false, launcherBusy = false;
let lastCommandKey = null, lastResultKey = "notRun", currentSetup = null;
let currentFrontendMode = "embedded";
let currentSnapshot = null;

function copy(key) { return translations[language][key] ?? translations.en[key] ?? key; }
function setState(node, text, good) { node.textContent = text; node.className = good === true ? "ok" : good === false ? "offline" : ""; }

function renderLanguage() {
  document.documentElement.lang = language;
  document.querySelectorAll("[data-copy]").forEach((node) => { node.textContent = copy(node.dataset.copy); });
  document.querySelector("#language").textContent = language === "en" ? "Español" : "English";
  renderFrontendSource(); document.querySelector("#backend-url").textContent = BACKEND_URL;
  document.querySelector("#last-command").textContent = lastCommandKey ? copy(lastCommandKey) : copy("noCommand");
  document.querySelector("#command-result").textContent = copy(lastResultKey); renderCommands(); if (currentSetup) renderSetup(currentSetup); if (currentSnapshot) renderHostMetrics(currentSnapshot.nativeHostMetrics);
}

function renderHostMetrics(metrics) {
  const available = metrics?.available === true;
  setState(document.querySelector("#host-metrics-status"), copy(available ? "hostNative" : "serverAgentRecommended"), available ? true : null);
  document.querySelector("#host-metrics-detail").textContent = available ? `${metrics.hostname ?? copy("unknown")} · ${Math.round(metrics.cpuPercent ?? 0)}% CPU · ${Math.round(metrics.memoryPercent ?? 0)}% RAM` : copy("hostMetricsUnavailable");
}

function publishNativeMetrics(metrics) {
  const frame = document.querySelector("#platform-frame");
  if (!frame?.contentWindow || !metrics) return;
  const origin = currentFrontendMode === "development" ? new URL(FRONTEND_URL).origin : window.location.origin;
  if (!origin || origin === "null") return;
  try { frame.contentWindow.postMessage({ type: "raventech-native-host-metrics", payload: metrics }, origin); } catch { /* Direct Tauri invocation remains available. */ }
}

function renderCommands() {
  document.querySelector("#commands").replaceChildren(...commands.filter((command) => !command.devOnly || currentFrontendMode === "development").map((command) => {
    const row = document.createElement("div"); row.className = "command";
    const name = document.createElement("label"); name.textContent = copy(command.label);
    const code = document.createElement("code"); code.textContent = command.text;
    const copyButton = document.createElement("button"); copyButton.type = "button"; copyButton.textContent = copy("copy");
    copyButton.addEventListener("click", async () => { try { await navigator.clipboard.writeText(command.text); document.querySelector("#message").textContent = copy("copied"); } catch { document.querySelector("#message").textContent = copy("copyFailed"); } });
    row.append(name, code);
    if (command.invoke) { const runButton = document.createElement("button"); runButton.type = "button"; runButton.textContent = copy("run"); runButton.disabled = launcherBusy; runButton.addEventListener("click", () => requestLauncherAction(command)); row.append(runButton); }
    else row.append(document.createElement("span"));
    row.append(copyButton); return row;
  }));
}

function renderFrontendSource() {
  document.querySelector("#frontend-url").textContent = currentFrontendMode === "development" ? FRONTEND_URL : copy("bundledAssets");
}

function renderSetup(setup) {
  currentSetup = setup; const valid = setup.configured && setup.configuredPathValid;
  setState(document.querySelector("#project-status"), valid ? copy("configured") : setup.repositoryFound ? copy("discovered") : copy("notConfigured"), valid || setup.repositoryFound);
  document.querySelector("#resolved-project").textContent = setup.repositoryPath ?? "—";
  const sourceKey = `source${setup.resolutionSource[0]?.toUpperCase() ?? ""}${setup.resolutionSource.slice(1)}`;
  document.querySelector("#resolution-source").textContent = copy(sourceKey);
  setState(document.querySelector("#scripts-status"), copy(setup.scriptsAvailable ? "available" : "unavailable"), setup.scriptsAvailable);
  document.querySelector("#next-action").textContent = copy(setup.nextAction);
  const input = document.querySelector("#project-path"); if (document.activeElement !== input && !input.value) input.value = setup.configuredPath ?? setup.repositoryPath ?? "";
}

function nextRuntimeAction(snapshot) {
  if (snapshot.setup.nextAction !== "checkRuntime") return snapshot.setup.nextAction;
  if (snapshot.dockerAvailability === "notDetected") return "installDocker";
  if (!snapshot.backend.reachable && snapshot.backendPortStatus === "occupied") return "backendPortConflict";
  if (!snapshot.backend.reachable) return snapshot.dockerAvailability === "installed" ? "startDocker" : "startBackend";
  if (!snapshot.readiness.healthy || snapshot.migrationStatus !== "ok") return "fixMigrations";
  if (snapshot.releaseMatches === false) return "releaseMismatchAction";
  if (snapshot.frontendMode === "development" && !snapshot.frontend.reachable && snapshot.frontendPortStatus === "occupied") return "frontendPortConflict";
  if (snapshot.frontendMode === "development" && !snapshot.frontend.healthy) return "startFrontend";
  return "runtimeReady";
}

function renderWizard(snapshot) {
  const projectReady = snapshot.setup.configuredPathValid;
  const prerequisitesReady = snapshot.setup.scriptsAvailable && snapshot.dockerAvailability !== "notDetected" && snapshot.backendPortStatus !== "occupied" && (snapshot.frontendMode !== "development" || snapshot.frontendPortStatus !== "occupied");
  const servicesReady = snapshot.backend.healthy && snapshot.readiness.healthy && snapshot.frontend.healthy && snapshot.releaseMatches === true && snapshot.migrationStatus === "ok";
  for (const [step, ready] of [["project", projectReady], ["prerequisites", prerequisitesReady], ["services", servicesReady]]) {
    const item = document.querySelector(`#step-${step}`); item.classList.toggle("complete", ready); item.classList.toggle("attention", !ready);
    setState(document.querySelector(`#step-${step}-state`), copy(ready ? "stepComplete" : "stepNeedsAction"), ready);
  }
}

async function saveProjectPath(event) {
  event.preventDefault(); const input = document.querySelector("#project-path"); const message = document.querySelector("#setup-message");
  if (!input.value.trim()) { message.textContent = copy("enterProjectPath"); message.className = "offline"; input.setAttribute("aria-invalid", "true"); input.focus(); return; }
  try { const result = await window.__TAURI__.core.invoke("bind_project_path", { projectPath: input.value }); message.textContent = copy(result.success ? "pathSaved" : "pathRejected"); message.className = result.success ? "ok" : "offline"; input.setAttribute("aria-invalid", String(!result.success)); renderSetup(result.setup); }
  catch { message.textContent = copy("pathRejected"); message.className = "offline"; }
  await refresh();
}

async function clearProjectPath() {
  const message = document.querySelector("#setup-message");
  try { const result = await window.__TAURI__.core.invoke("clear_project_path"); message.textContent = copy(result.success ? "pathCleared" : "commandFailed"); message.className = result.success ? "ok" : "offline"; document.querySelector("#project-path").value = ""; renderSetup(result.setup); }
  catch { message.textContent = copy("commandFailed"); message.className = "offline"; }
  await refresh();
}

function confirmLauncherAction(command) {
  if (!command.confirm) return Promise.resolve(true); const dialog = document.querySelector("#confirm-dialog");
  document.querySelector("#confirm-message").textContent = copy("confirmBody").replace("{action}", copy(command.label)); dialog.showModal();
  return new Promise((resolve) => dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"), { once: true }));
}

async function requestLauncherAction(command) {
  if (launcherBusy || !(await confirmLauncherAction(command))) return;
  launcherBusy = true; lastCommandKey = command.label; lastResultKey = "running"; renderLanguage();
  const resultNode = document.querySelector("#command-result"), outputNode = document.querySelector("#command-output"); resultNode.className = ""; outputNode.hidden = true; outputNode.textContent = "";
  try { const result = await window.__TAURI__.core.invoke(command.invoke); lastResultKey = !result.scriptAvailable ? "commandUnavailable" : result.timedOut ? "commandTimedOut" : result.success ? "commandSucceeded" : "commandFailed"; if (result.output) { outputNode.textContent = result.output; outputNode.hidden = false; } }
  catch { lastResultKey = "commandFailed"; }
  launcherBusy = false; renderLanguage(); resultNode.className = lastResultKey === "commandSucceeded" ? "ok" : "offline"; await refresh();
}

function paint(id, state, detail = "") {
  const node = document.querySelector(id); setState(node, copy(state), state === "ready" || state === "reachable" || state === "available" || state === "embedded");
  const detailNode = document.querySelector(id.replace("-status", "-detail")); if (detailNode) detailNode.textContent = detail;
}
function showPlatform() { statusPinned = false; platformOpen = true; document.querySelector("#status-view").hidden = true; document.querySelector(".topbar").hidden = true; document.querySelector("#platform-view").hidden = false; const frame = document.querySelector("#platform-frame"); const target = currentFrontendMode === "development" ? FRONTEND_URL : EMBEDDED_FRONTEND_URL; if (frame.dataset.mode !== currentFrontendMode) { frame.src = target; frame.dataset.mode = currentFrontendMode; } }
function showStatus(pin = true) { statusPinned = pin; platformOpen = false; document.querySelector("#platform-view").hidden = true; document.querySelector(".topbar").hidden = false; document.querySelector("#status-view").hidden = false; }
function setGuidance(name) { ["backend", "readiness", "frontend"].forEach((item) => { document.querySelector(`#${item}-guidance`).hidden = item !== name; }); }

function renderChecklist(snapshot) {
  setState(document.querySelector("#check-repository"), copy(snapshot.setup.repositoryFound ? "available" : "unavailable"), snapshot.setup.repositoryFound);
  const dockerKey = snapshot.dockerAvailability === "running" ? "runningDocker" : snapshot.dockerAvailability === "installed" ? "installedDocker" : "notDetected";
  setState(document.querySelector("#check-docker"), copy(dockerKey), snapshot.dockerAvailability === "running" ? true : snapshot.dockerAvailability === "notDetected" ? false : null);
  for (const [id, status] of [["#check-backend-port", snapshot.backendPortStatus], ["#check-frontend-port", snapshot.frontendPortStatus]]) setState(document.querySelector(id), copy(status === "available" ? "portAvailable" : status), status === "application" || status === "notRequired" ? true : status === "occupied" ? false : null);
  setState(document.querySelector("#check-release"), snapshot.releaseMatches == null ? copy("unknown") : copy(snapshot.releaseMatches ? "matches" : "mismatch"), snapshot.releaseMatches);
  setState(document.querySelector("#check-migrations"), snapshot.migrationStatus == null ? copy("unknown") : copy(snapshot.migrationStatus === "ok" ? "ready" : "pending"), snapshot.migrationStatus === "ok" ? true : snapshot.migrationStatus == null ? null : false);
}

function renderSnapshot(snapshot) {
  currentSnapshot = snapshot;
  currentFrontendMode = snapshot.frontendMode === "development" ? "development" : "embedded"; renderFrontendSource(); renderCommands();
  renderSetup(snapshot.setup); renderChecklist(snapshot); renderWizard(snapshot); document.querySelector("#next-action").textContent = copy(nextRuntimeAction(snapshot));
  const backendState = !snapshot.backend.reachable ? "unreachable" : snapshot.backend.healthy ? "reachable" : "degraded";
  const readinessState = !snapshot.readiness.reachable ? "unreachable" : snapshot.readiness.healthy ? "ready" : "degraded";
  const frontendState = currentFrontendMode === "embedded" ? "embedded" : !snapshot.frontend.reachable ? "unreachable" : snapshot.frontend.healthy ? "reachable" : "degraded";
  paint("#backend-status", backendState, snapshot.backend.status ?? ""); paint("#ready-status", readinessState, snapshot.readiness.status ?? "");
  setState(document.querySelector("#release-status"), snapshot.releaseVersion ?? copy("unavailable"), snapshot.releaseMatches ?? false);
  document.querySelector("#release-detail").textContent = snapshot.release.httpStatus ? `HTTP ${snapshot.release.httpStatus}` : copy("unknown");
  paint("#frontend-status", frontendState, currentFrontendMode === "embedded" ? copy("bundledAssets") : snapshot.frontend.httpStatus ? `HTTP ${snapshot.frontend.httpStatus}` : "");
  const dockerState = snapshot.dockerServicesStatus ?? (!snapshot.backend.reachable ? "unknown" : "degraded"); paint("#docker-status", dockerState, snapshot.dockerServicesStatus ? copy(dockerState) : copy("unknown"));
  renderHostMetrics(snapshot.nativeHostMetrics); publishNativeMetrics(snapshot.nativeHostMetrics);
  const allReady = snapshot.setup.configuredPathValid && snapshot.backend.healthy && snapshot.readiness.healthy && snapshot.frontend.healthy && snapshot.releaseMatches === true && snapshot.migrationStatus === "ok";
  const summary = document.querySelector("#summary"), summaryText = document.querySelector("#summary-text"), openButton = document.querySelector("#open-platform"); openButton.hidden = !allReady;
  if (!snapshot.setup.configuredPathValid) { summary.className = "summary warning"; summaryText.textContent = copy("setupMessage"); setGuidance(""); }
  else if (!snapshot.backend.reachable) { summary.className = "summary error"; summaryText.textContent = copy("backendMessage"); setGuidance("backend"); }
  else if (!snapshot.backend.healthy || !snapshot.readiness.healthy) { summary.className = "summary warning"; summaryText.textContent = copy("readinessMessage"); setGuidance("readiness"); }
  else if (currentFrontendMode === "development" && !snapshot.frontend.healthy) { summary.className = "summary warning"; summaryText.textContent = copy("frontendMessage"); setGuidance("frontend"); }
  else { summary.className = "summary success"; summaryText.textContent = copy("readyMessage"); setGuidance(""); }
  document.querySelector("#platform-summary").textContent = snapshot.releaseVersion ? `${copy("platformHealthy")} · ${snapshot.releaseVersion}` : copy("platformHealthy");
  if (allReady && !previouslyReady && !statusPinned) showPlatform(); if (!allReady && platformOpen) { document.querySelector("#message").textContent = copy("platformDegraded"); showStatus(false); } previouslyReady = allReady;
}

async function refresh() {
  if (checking) return; checking = true; ["#backend-status", "#ready-status", "#release-status", "#frontend-status", "#docker-status"].forEach((id) => paint(id, "checking"));
  try { renderSnapshot(await window.__TAURI__.core.invoke("probe_local_services")); }
  catch { renderSnapshot({ backend: { reachable: false, healthy: false }, readiness: { reachable: false, healthy: false }, release: { reachable: false, healthy: false }, frontend: { reachable: true, healthy: true, status: "embedded" }, frontendMode: "embedded", releaseVersion: null, dockerServicesStatus: null, dockerAvailability: "notDetected", backendPortStatus: "available", frontendPortStatus: "notRequired", releaseMatches: null, migrationStatus: null, setup: { configured: false, configuredPath: null, configuredPathValid: false, repositoryFound: false, repositoryPath: null, resolutionSource: "copyOnly", composeAvailable: false, frontendAvailable: false, backendAvailable: false, scriptsAvailable: false, nextAction: "bindProjectPath" } }); }
  finally { checking = false; }
}

document.querySelector("#language").addEventListener("click", () => { language = language === "en" ? "es" : "en"; localStorage.setItem("raventech-desktop-language", language); renderLanguage(); refresh(); });
document.querySelector("#refresh").addEventListener("click", refresh); document.querySelector("#show-status").addEventListener("click", () => showStatus(true)); document.querySelector("#open-platform").addEventListener("click", showPlatform);
document.querySelector("#project-form").addEventListener("submit", saveProjectPath); document.querySelector("#clear-project-path").addEventListener("click", clearProjectPath);
document.querySelector("#project-path").addEventListener("input", (event) => event.currentTarget.removeAttribute("aria-invalid"));
document.querySelector("#platform-frame").addEventListener("load", () => publishNativeMetrics(currentSnapshot?.nativeHostMetrics));
renderLanguage(); refresh(); window.setInterval(refresh, 15_000);
