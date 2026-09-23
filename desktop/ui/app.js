const FRONTEND_URL = "http://localhost:5173";
const BACKEND_URL = "http://localhost:8000";
const EMBEDDED_FRONTEND_URL = "./app/";

const translations = {
  en: {
    runtimeEyebrow: "NATIVE APPLICATION LIFECYCLE", runtimeTitle: "Local Runtime", runtimeIntro: "The desktop owns its managed PostgreSQL, backend, and worker processes. External PostgreSQL remains supported.",
    postgresRequiredAction: "Check the selected database mode and PostgreSQL runtime status.", runtimeStartingAction: "The desktop is starting PostgreSQL, the native backend, and worker.", nativeBackendMessage: "The native backend is starting or unavailable. Review Local Runtime for the safe reason and next step.", dbLocalOnly: "Loopback only", dbUptime: "Uptime", dbRestarts: "Restarts", dbError_managed_port_conflict: "Port 55432 is occupied. RavenTech did not contact or stop that process.", dbError_postgres_artifacts_missing: "The bundled PostgreSQL 16 runtime is unavailable or incomplete. Repair the desktop installation.", dbError_cluster_marker_missing: "An existing cluster has no RavenTech ownership marker. It was left untouched.", dbError_unknown_data_directory: "The managed database directory contains unknown data and was left untouched.", dbError_database_secret_unavailable: "The managed database credential is unavailable or invalid. Data was preserved.", dbError_migration_failed: "Database migration did not complete. The database was preserved.", dbError_postgres_exited: "Managed PostgreSQL exited unexpectedly. Data was preserved; a bounded restart may be attempted.",
    runtimeBackend: "Native Backend", runtimeWorker: "Background Worker", runtimePostgres: "PostgreSQL", runtimeFrontend: "Embedded Frontend", runtimeMode: "Runtime profile", ownershipOwned: "Owned by this desktop", ownershipExternal: "Externally managed", ownershipNone: "Not started", runtimeHealthy: "Healthy", runtimeWaiting: "Waiting", runtimeStarting: "Starting", runtimeRunning: "Running", runtimeFailed: "Failed", runtimeStopped: "Stopped", runtimeUnavailable: "Unavailable", runtimeOptional: "Not required", runtimeRestart: "Restart", runtimeStop: "Stop", runtimeStart: "Start", runtimeRetry: "Retry", runtimeConfirm: "Confirm stopping/restarting this local component? Active requests or jobs may be interrupted.", runtimeControlFailed: "The requested action was not accepted. Only components owned by this desktop can be stopped.", runtimePid: "PID", runtimeError: "Reason", runtimeRedis: "Redis (optional)", runtimeCelery: "Celery (compatibility only)", dbManaged: "Managed local database", dbExternal: "External database", dbVersion: "Version", dbPort: "Port", dbMigration: "Migrations",
    desktopEyebrow: "NATIVE DESKTOP STARTUP", desktopTitle: "Desktop runtime", desktopIntro: "RavenTech starts its database, backend, worker, and embedded interface automatically.", nativeProfile: "Native PostgreSQL runtime", stageApplication: "Application", stageDatabase: "Database", stageBackend: "Backend", stageWorker: "Worker", stageMonitoring: "Host monitoring", stageReady: "Ready", nativePass: "Ready", nativeFail: "Needs attention", nativePending: "Starting", nativeCompatibility: "Docker is optional. Redis and Celery are not required. PostgreSQL remains required.", acceptEmbedded: "Embedded UI", acceptMigrations: "Migrations", acceptJobs: "Native jobs", nativeHeroTitle: "RavenTech desktop runtime", nativeHeroIntro: "Local services start automatically. No repository setup or separate terminal steps are needed.", nativeReadyTitle: "RavenTech is ready", nativeReadyMessage: "RavenTech is ready. Your embedded workspace is available.", nativeOpenWorkspace: "Open RavenTech",
    prototype: "RC6 local setup assistant", refresh: "Check again", eyebrow: "LOCAL SERVICE STATUS",
    title: "Local operator workspace", intro: "Validate the project once, then check and control only the approved local services.",
    setupEyebrow: "FIRST-RUN SETUP", setupTitle: "Bind the local RavenTech project", setupBody: "Enter the repository root manually. The desktop validates fixed markers and stores only the validated path.",
    projectPath: "Project path", validateSave: "Validate and save", clearPath: "Clear saved path", resolvedPath: "Resolved project", resolutionSource: "Resolution source", scriptAvailability: "Approved scripts", nextAction: "Next required action",
    wizardProject: "Project", wizardPrerequisites: "Prerequisites", wizardServices: "Local services", stepComplete: "Complete", stepNeedsAction: "Needs action", distributionNote: "Portable and installed builds use this same validated path. Installed builds normally require you to enter it once.",
    pathSaved: "Project path validated and saved.", pathRejected: "That path is not a complete RavenTech repository. Verify the repository root and six approved scripts. Nothing was saved.", enterProjectPath: "Enter the local RavenTech repository root before validating.", pathCleared: "Saved path cleared. Automatic discovery remains available.",
    configured: "Configured", discovered: "Discovered", notConfigured: "Not configured", sourceConfigured: "Saved preference", sourceCurrentDirectory: "Current directory", sourceDevelopmentRelative: "Development-relative", sourceCopyOnly: "Copy-only fallback",
    bindProjectPath: "Enter and save the RavenTech repository root.", correctProjectPath: "Correct the saved project path.", restoreScripts: "Restore the six approved local scripts.", checkRuntime: "Check local runtime prerequisites.",
    startDocker: "Start Docker Desktop, then start the platform.", installDocker: "Install Docker Desktop manually; nothing is installed automatically.", backendPortConflict: "Port 8000 is occupied by another service.", frontendPortConflict: "Port 5173 is occupied by another service.",
    startBackend: "Start the approved local Docker services.", startFrontend: "Start the local Vite frontend for development/browser mode.", fixMigrations: "Use the approved platform start/check flow to resolve pending migrations.", releaseMismatchAction: "The backend release does not match 5.0.0-rc6.", runtimeReady: "Local runtime is ready.",
    backendHealth: "Backend", readiness: "Readiness", release: "Release", frontend: "Frontend", dockerServices: "Docker services", runtimeChecklist: "Runtime checklist", repoStructure: "Repository structure", dockerAvailability: "Docker availability", backendPort: "Port 8000", frontendPort: "Port 5173 (development only)", releaseMatch: "Expected release", migrationState: "Migrations",
    hostMetrics: "Server host metrics", hostNative: "Host native metrics", serverAgentRecommended: "Run ServerHost agent", hostMetricsUnavailable: "Native metrics unavailable; the Monitoring Center will prefer a fresh ServerHost agent and label Docker metrics as fallback.",
    runningDocker: "Running", installedDocker: "Installed, not confirmed running", notDetected: "Not detected", application: "RavenTech responding", occupied: "Occupied by another service", portAvailable: "Available; service not listening", matches: "Matches", mismatch: "Mismatch", pending: "Pending or degraded",
    helpTitle: "Controlled local launcher", helpBody: "Approved actions use six fixed scripts from the validated repository. Copy remains available if runtime execution is unavailable.",
    backendHelpTitle: "Backend is not reachable", backendHelpBody: "Check the selected database mode and local runtime status. Docker is needed only for Docker compatibility mode.", readinessHelpTitle: "Backend dependencies are not ready", readinessHelpBody: "A dependency or migration is degraded. Use Check health for a sanitized diagnosis.", frontendHelpTitle: "Frontend is not reachable", frontendHelpBody: "Run the Vite development server from the validated repository. It is not auto-installed or started outside the approved script flow.",
    endpoints: "Local endpoints", frontendUrl: "Frontend source", backendUrl: "Backend URL", firewallTitle: "Windows firewall guidance", firewallBody: "RavenTech uses backend loopback port 8000. Port 5173 is used only for development/browser mode. Do not approve public-network exposure; review any firewall prompt before continuing.", connected: "Frontend workspace", showStatus: "Service status", openWorkspace: "Open local workspace", checking: "Checking…", reachable: "Accessible", unreachable: "Not accessible", ready: "Ready", degraded: "Degraded", embedded: "Embedded", bundledAssets: "Bundled React assets", notRequired: "Not required", available: "Available", unavailable: "Unavailable", unknown: "Unknown",
    start: "Start platform", stop: "Stop platform", restart: "Restart platform", check: "Check health", applyLanConfig: "Apply fixed LAN profile", openFrontend: "Open frontend", frontendCommand: "Run frontend dev", backendCommand: "Run Docker services", copy: "Copy", run: "Run", copied: "Command copied. Nothing was executed.", copyFailed: "Clipboard access is unavailable. Select the visible command text and copy it manually.",
    lastCommand: "Last command", noCommand: "No launcher action has run.", notRun: "Not run", running: "Running approved script…", commandSucceeded: "Approved script completed.", commandFailed: "Approved script failed.", commandUnavailable: "Validated repository script unavailable; use Copy.", commandTimedOut: "Approved script timed out; check status before retrying.",
    confirmTitle: "Confirm local action", confirmBody: "Run the approved {action} script from the validated project? Review the visible command first; this changes bounded local state.", cancel: "Cancel", confirm: "Confirm",
    readyMessage: "Project, backend, dependencies, and frontend are ready.", setupMessage: "Complete first-run project binding to make installed and portable launches reliable.", backendMessage: "Backend is not accessible. Review Docker and port 8000 below.", readinessMessage: "Backend is accessible, but a required dependency or migration needs action.", frontendMessage: "Backend is ready. Start Vite only for development/browser mode.", platformHealthy: "Backend ready", platformDegraded: "Service problem detected; returning to status."
  },
  es: {
    runtimeEyebrow: "CICLO DE VIDA NATIVO DE LA APLICACIÓN", runtimeTitle: "Entorno local", runtimeIntro: "El escritorio controla PostgreSQL administrado, el backend y el worker. También admite PostgreSQL externo.",
    postgresRequiredAction: "Revisa el modo de base de datos y el estado del entorno local.", runtimeStartingAction: "El escritorio está iniciando PostgreSQL, el backend y el worker nativos.", nativeBackendMessage: "El backend nativo está iniciando o no está disponible. Consulta Entorno local para conocer el motivo y el siguiente paso.", dbLocalOnly: "Solo loopback", dbUptime: "Tiempo activo", dbRestarts: "Reinicios", dbError_managed_port_conflict: "El puerto 55432 está ocupado. RavenTech no se conectó ni detuvo ese proceso.", dbError_postgres_artifacts_missing: "El runtime PostgreSQL 16 incluido no está disponible o está incompleto. Repara la instalación.", dbError_cluster_marker_missing: "El clúster existente no tiene un marcador de RavenTech. Se dejó intacto.", dbError_unknown_data_directory: "El directorio de base de datos contiene datos desconocidos y se dejó intacto.", dbError_database_secret_unavailable: "La credencial administrada no está disponible o no es válida. Se conservaron los datos.", dbError_migration_failed: "La migración no terminó. Se conservó la base de datos.", dbError_postgres_exited: "PostgreSQL administrado se cerró inesperadamente. Se conservaron los datos; se puede intentar un reinicio limitado.",
    runtimeBackend: "Backend nativo", runtimeWorker: "Worker en segundo plano", runtimePostgres: "PostgreSQL", runtimeFrontend: "Frontend integrado", runtimeMode: "Perfil del entorno", ownershipOwned: "Controlado por este escritorio", ownershipExternal: "Administrado externamente", ownershipNone: "Sin iniciar", runtimeHealthy: "Saludable", runtimeWaiting: "En espera", runtimeStarting: "Iniciando", runtimeRunning: "En ejecución", runtimeFailed: "Error", runtimeStopped: "Detenido", runtimeUnavailable: "No disponible", runtimeOptional: "No requerido", runtimeRestart: "Reiniciar", runtimeStop: "Detener", runtimeStart: "Iniciar", runtimeRetry: "Reintentar", runtimeConfirm: "¿Confirmas detener o reiniciar este componente local? Las solicitudes o tareas activas pueden interrumpirse.", runtimeControlFailed: "No se aceptó la acción. Solo se pueden detener componentes controlados por este escritorio.", runtimePid: "PID", runtimeError: "Motivo", runtimeRedis: "Redis (opcional)", runtimeCelery: "Celery (solo compatibilidad)", dbManaged: "Base de datos local administrada", dbExternal: "Base de datos externa", dbVersion: "Versión", dbPort: "Puerto", dbMigration: "Migraciones",
    desktopEyebrow: "INICIO NATIVO DEL ESCRITORIO", desktopTitle: "Entorno del escritorio", desktopIntro: "RavenTech inicia automáticamente la base de datos, el backend, el worker y la interfaz integrada.", nativeProfile: "Runtime PostgreSQL nativo", stageApplication: "Aplicación", stageDatabase: "Base de datos", stageBackend: "Backend", stageWorker: "Worker", stageMonitoring: "Monitoreo del host", stageReady: "Listo", nativePass: "Listo", nativeFail: "Requiere atención", nativePending: "Iniciando", nativeCompatibility: "Docker es opcional. Redis y Celery no son necesarios. PostgreSQL sigue siendo requerido.", acceptEmbedded: "Interfaz integrada", acceptMigrations: "Migraciones", acceptJobs: "Tareas nativas", nativeHeroTitle: "Runtime de RavenTech Desktop", nativeHeroIntro: "Los servicios locales se inician automáticamente. No se necesita configurar una ruta de repositorio ni usar una terminal.", nativeReadyTitle: "RavenTech está listo", nativeReadyMessage: "RavenTech está listo. El espacio integrado está disponible.", nativeOpenWorkspace: "Abrir RavenTech",
    prototype: "Asistente de configuración local RC6", refresh: "Comprobar de nuevo", eyebrow: "ESTADO DE SERVICIOS LOCALES",
    title: "Espacio de trabajo del operador", intro: "Valida el proyecto una vez y después comprueba y controla solo los servicios locales aprobados.",
    setupEyebrow: "CONFIGURACIÓN INICIAL", setupTitle: "Vincular el proyecto local de RavenTech", setupBody: "Introduce manualmente la raíz del repositorio. El escritorio valida marcadores fijos y guarda solo la ruta validada.",
    projectPath: "Ruta del proyecto", validateSave: "Validar y guardar", clearPath: "Borrar ruta guardada", resolvedPath: "Proyecto resuelto", resolutionSource: "Origen de resolución", scriptAvailability: "Scripts aprobados", nextAction: "Siguiente acción requerida",
    wizardProject: "Proyecto", wizardPrerequisites: "Requisitos", wizardServices: "Servicios locales", stepComplete: "Completo", stepNeedsAction: "Requiere acción", distributionNote: "Las versiones portable e instalada usan esta misma ruta validada. La versión instalada normalmente requiere introducirla una vez.",
    pathSaved: "Ruta del proyecto validada y guardada.", pathRejected: "La ruta no es un repositorio completo de RavenTech. Verifica la raíz y los seis scripts aprobados. No se guardó nada.", enterProjectPath: "Introduce la raíz del repositorio local RavenTech antes de validar.", pathCleared: "Ruta guardada borrada. El descubrimiento automático sigue disponible.",
    configured: "Configurada", discovered: "Detectada", notConfigured: "Sin configurar", sourceConfigured: "Preferencia guardada", sourceCurrentDirectory: "Directorio actual", sourceDevelopmentRelative: "Ruta relativa de desarrollo", sourceCopyOnly: "Alternativa de solo copia",
    bindProjectPath: "Introduce y guarda la raíz del repositorio RavenTech.", correctProjectPath: "Corrige la ruta del proyecto guardada.", restoreScripts: "Restaura los seis scripts locales aprobados.", checkRuntime: "Comprueba los requisitos del entorno local.",
    startDocker: "Inicia Docker Desktop y después la plataforma.", installDocker: "Instala Docker Desktop manualmente; nada se instala automáticamente.", backendPortConflict: "El puerto 8000 está ocupado por otro servicio.", frontendPortConflict: "El puerto 5173 está ocupado por otro servicio.",
    startBackend: "Inicia los servicios Docker locales aprobados.", startFrontend: "Inicia el frontend Vite solo para desarrollo/modo navegador.", fixMigrations: "Usa el inicio/comprobación aprobado para resolver migraciones pendientes.", releaseMismatchAction: "La versión del backend no coincide con 5.0.0-rc6.", runtimeReady: "El entorno local está listo.",
    backendHealth: "Backend", readiness: "Disponibilidad", release: "Versión", frontend: "Frontend", dockerServices: "Servicios Docker", runtimeChecklist: "Lista del entorno", repoStructure: "Estructura del repositorio", dockerAvailability: "Disponibilidad de Docker", backendPort: "Puerto 8000", frontendPort: "Puerto 5173 (solo desarrollo)", releaseMatch: "Versión esperada", migrationState: "Migraciones",
    hostMetrics: "Métricas del host servidor", hostNative: "Métricas nativas del host", serverAgentRecommended: "Ejecutar agente ServerHost", hostMetricsUnavailable: "Las métricas nativas no están disponibles; el Centro de Monitoreo preferirá un agente ServerHost reciente y etiquetará Docker como alternativa.",
    runningDocker: "En ejecución", installedDocker: "Instalado, ejecución no confirmada", notDetected: "No detectado", application: "RavenTech responde", occupied: "Ocupado por otro servicio", portAvailable: "Disponible; servicio sin escuchar", matches: "Coincide", mismatch: "No coincide", pending: "Pendientes o degradadas",
    helpTitle: "Iniciador local controlado", helpBody: "Las acciones aprobadas usan seis scripts fijos del repositorio validado. Copiar sigue disponible si la ejecución no está disponible.",
    backendHelpTitle: "No se puede acceder al backend", backendHelpBody: "Revisa el modo de base de datos y el estado del entorno local. Docker solo se necesita en el modo de compatibilidad Docker.", readinessHelpTitle: "Las dependencias del backend no están listas", readinessHelpBody: "Una dependencia o migración está degradada. Usa Comprobar salud para un diagnóstico sanitizado.", frontendHelpTitle: "No se puede acceder al frontend", frontendHelpBody: "Ejecuta el servidor Vite desde el repositorio validado. No se instala ni inicia automáticamente fuera del flujo aprobado.",
    endpoints: "Endpoints locales", frontendUrl: "Origen del frontend", backendUrl: "URL del backend", firewallTitle: "Guía del firewall de Windows", firewallBody: "RavenTech usa el puerto local 8000 para el backend. El puerto 5173 solo se usa en desarrollo/modo navegador. No autorices exposición en redes públicas; revisa cualquier aviso del firewall antes de continuar.", connected: "Espacio del frontend", showStatus: "Estado de servicios", openWorkspace: "Abrir espacio local", checking: "Comprobando…", reachable: "Accesible", unreachable: "No accesible", ready: "Listo", degraded: "Degradado", embedded: "Integrado", bundledAssets: "Recursos React incluidos", notRequired: "No requerido", available: "Disponible", unavailable: "No disponible", unknown: "Desconocido",
    start: "Iniciar plataforma", stop: "Detener plataforma", restart: "Reiniciar plataforma", check: "Comprobar salud", applyLanConfig: "Aplicar perfil LAN fijo", openFrontend: "Abrir frontend", frontendCommand: "Ejecutar frontend dev", backendCommand: "Ejecutar servicios Docker", copy: "Copiar", run: "Ejecutar", copied: "Comando copiado. No se ejecutó nada.", copyFailed: "El portapapeles no está disponible. Selecciona el comando visible y cópialo manualmente.",
    lastCommand: "Último comando", noCommand: "No se ha ejecutado ninguna acción.", notRun: "Sin ejecutar", running: "Ejecutando script aprobado…", commandSucceeded: "El script aprobado terminó correctamente.", commandFailed: "El script aprobado falló.", commandUnavailable: "Script del repositorio validado no disponible; usa Copiar.", commandTimedOut: "El script agotó el tiempo; comprueba el estado antes de reintentar.",
    confirmTitle: "Confirmar acción local", confirmBody: "¿Ejecutar el script aprobado de {action} desde el proyecto validado? Revisa primero el comando visible; esto cambia un estado local limitado.", cancel: "Cancelar", confirm: "Confirmar",
    readyMessage: "El proyecto, backend, dependencias y frontend están listos.", setupMessage: "Completa la vinculación inicial para que los inicios instalados y portables sean fiables.", backendMessage: "El backend no está accesible. Revisa Docker y el puerto 8000.", readinessMessage: "El backend responde, pero una dependencia o migración requiere atención.", frontendMessage: "El backend está listo. Inicia Vite solo para desarrollo/modo navegador.", platformHealthy: "Backend listo", platformDegraded: "Se detectó un problema; regresando al estado."
  }
};

const commands = Object.freeze([
  { label: "start", text: ".\\scripts\\local\\start_platform.ps1", invoke: "start_platform", confirm: true },
  { label: "stop", text: ".\\scripts\\local\\stop_platform.ps1", invoke: "stop_platform", confirm: true },
  { label: "restart", text: ".\\scripts\\local\\restart_platform.ps1", invoke: "restart_platform", confirm: true },
  { label: "check", text: ".\\scripts\\local\\check_platform.ps1", invoke: "check_platform", confirm: false },
  { label: "applyLanConfig", text: ".\\scripts\\local\\apply_lan_monitoring_config.ps1", invoke: "apply_lan_monitoring_config", confirm: true, confirmedArgument: true },
  { label: "openFrontend", text: ".\\scripts\\local\\open_platform.ps1 -Target frontend", invoke: "open_local_frontend", confirm: false, devOnly: true },
  { label: "frontendCommand", text: "cd frontend; npm run dev", devOnly: true },
  { label: "backendCommand", text: "docker compose up -d postgres redis backend celery-worker" }
]);

let language = localStorage.getItem("raventech-desktop-language") === "es" ? "es" : "en";
let checking = false, platformOpen = false, statusPinned = false, previouslyReady = false, launcherBusy = false;
let lastCommandKey = null, lastResultKey = "notRun", currentSetup = null;
let currentFrontendMode = "embedded";
let currentSnapshot = null;
let currentNativeRuntime = null;
let runtimeActionBusy = false;

function copy(key) { return translations[language][key] ?? translations.en[key] ?? key; }
function setState(node, text, good) { node.textContent = text; node.className = good === true ? "ok" : good === false ? "offline" : ""; }

function renderLanguage() {
  document.documentElement.lang = language;
  document.querySelectorAll("[data-copy]").forEach((node) => { node.textContent = copy(node.dataset.copy); });
  document.querySelector("#language").textContent = language === "en" ? "Español" : "English";
  renderFrontendSource(); document.querySelector("#backend-url").textContent = BACKEND_URL;
  document.querySelector("#last-command").textContent = lastCommandKey ? copy(lastCommandKey) : copy("noCommand");
  document.querySelector("#command-result").textContent = copy(lastResultKey); renderCommands(); if (currentSetup) renderSetup(currentSetup); if (currentSnapshot) renderHostMetrics(currentSnapshot.nativeHostMetrics);
  if (currentSnapshot && currentNativeRuntime?.runtimeMode === "desktop") {
    const ready = renderNativeAcceptance(currentSnapshot);
    document.querySelector("#hero-title").textContent = copy(ready ? "nativeReadyTitle" : "nativeHeroTitle");
    document.querySelector("#hero-intro").textContent = copy("nativeHeroIntro");
    document.querySelector("#open-platform").textContent = copy("nativeOpenWorkspace");
  }
}

function renderHostMetrics(metrics) {
  const available = metrics?.available === true;
  setState(document.querySelector("#host-metrics-status"), copy(available ? "hostNative" : "serverAgentRecommended"), available ? true : null);
  document.querySelector("#host-metrics-detail").textContent = available ? `${metrics.hostname ?? copy("unknown")} · ${Math.round(metrics.cpuPercent ?? 0)}% CPU · ${Math.round(metrics.memoryPercent ?? 0)}% RAM` : copy("hostMetricsUnavailable");
}

function runtimeLabel(value) {
  const key = ({ healthy: "runtimeHealthy", ready: "runtimeHealthy", running: "runtimeRunning", starting: "runtimeStarting", waiting: "runtimeWaiting", failed: "runtimeFailed", stopped: "runtimeStopped", unavailable: "runtimeUnavailable", none: "ownershipNone", owned: "ownershipOwned", external: "ownershipExternal", not_required: "runtimeOptional" })[value];
  return key ? copy(key) : value ?? copy("unknown");
}

function renderNativeRuntime(status) {
  if (!status) return;
  currentNativeRuntime = status;
  document.querySelector("#runtime-profile").textContent = `${copy("runtimeMode")}: ${runtimeLabel(status.runtimeMode)}`;
  document.querySelector("#runtime-message").textContent = status.postgresql?.mode === "managed" && status.postgresql?.state === "failed" ? copy("postgresRequiredAction") : (status.lastMessages?.at(-1) ?? "");
  const root = document.querySelector("#native-runtime");
  const components = [
    ["runtimeBackend", "backend", status.backend], ["runtimeWorker", "worker", status.worker],
    ["runtimePostgres", "postgres", status.postgresql],
    ["runtimeFrontend", "frontend", { state: status.embeddedFrontend, ownership: "none", actionsAvailable: false }],
  ];
  root.replaceChildren(...components.map(([label, name, item]) => {
    const row = document.createElement("article"); row.className = "runtime-row";
    const heading = document.createElement("strong"); heading.textContent = copy(label);
    const uptime = name === "postgres" && item?.startedAtUnixMs ? Math.max(0, Math.floor((Date.now() - Number(item.startedAtUnixMs)) / 1000)) : null;
    const facts = document.createElement("span"); facts.textContent = `${runtimeLabel(item?.state)} · ${runtimeLabel(item?.ownership)}${item?.pid ? ` · ${copy("runtimePid")} ${item.pid}` : ""}${name === "postgres" ? ` · ${item?.version ?? copy("unknown")} · ${copy("runtimeMode")}: ${item?.mode === "managed" ? copy("dbManaged") : copy("dbExternal")}${item?.port ? ` · ${copy("dbLocalOnly")}: 127.0.0.1:${item.port}` : ""} · ${copy("dbMigration")}: ${item?.migrationState ?? copy("unknown")}${uptime !== null ? ` · ${copy("dbUptime")}: ${uptime}s` : ""} · ${copy("dbRestarts")}: ${item?.restartCount ?? 0}` : ""}`;
    row.append(heading, facts);
    if (item?.lastError) { const error = document.createElement("small"); error.textContent = `${copy("runtimeError")}: ${name === "postgres" && item.lastErrorCode && translations[locale]?.[`dbError_${item.lastErrorCode}`] ? copy(`dbError_${item.lastErrorCode}`) : item.lastError}`; row.append(error); }
    if (name === "backend" || name === "worker" || (name === "postgres" && item?.mode === "managed")) {
      const actions = document.createElement("div"); actions.className = "runtime-actions";
      for (const action of ["start", "restart", "stop"]) {
        const button = document.createElement("button"); button.type = "button"; button.textContent = copy(`runtime${action[0].toUpperCase()}${action.slice(1)}`);
        button.disabled = runtimeActionBusy || (action !== "start" && !(item?.ownership === "owned" && item?.actionsAvailable)) || (action === "start" && ["running", "healthy", "starting"].includes(item?.state));
        button.addEventListener("click", () => requestRuntimeAction(name === "postgres" ? "postgresql" : name, action)); actions.append(button);
      }
      row.append(actions);
    }
    return row;
  }));
  const optionals = document.createElement("p"); optionals.className = "runtime-optionals";
  optionals.textContent = `${copy("runtimeRedis")}: ${runtimeLabel(status.redis?.state)} · ${copy("runtimeCelery")}: ${runtimeLabel(status.celery?.state)}`;
  root.append(optionals);
  publishNativeRuntime(status);
}

function publishNativeRuntime(status) {
  const frame = document.querySelector("#platform-frame");
  if (!frame?.contentWindow || !status) return;
  const origin = currentFrontendMode === "development" ? new URL(FRONTEND_URL).origin : window.location.origin;
  if (!origin || origin === "null") return;
  try { frame.contentWindow.postMessage({ type: "raventech-native-runtime-status", payload: status }, origin); } catch { /* Runtime status remains available in the shell. */ }
}

async function requestRuntimeAction(component, action) {
  if (runtimeActionBusy) return;
  if (action !== "start") {
    const dialog = document.querySelector("#confirm-dialog"); document.querySelector("#confirm-message").textContent = copy("runtimeConfirm"); dialog.showModal();
    const confirmed = await new Promise((resolve) => dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"), { once: true }));
    if (!confirmed) return;
  }
  runtimeActionBusy = true;
  try { await window.__TAURI__.core.invoke("control_native_runtime_component", { component, action, confirmed: action !== "start" }); document.querySelector("#runtime-message").textContent = ""; }
  catch { document.querySelector("#runtime-message").textContent = copy("runtimeControlFailed"); }
  finally { runtimeActionBusy = false; }
  await refresh();
}

function publishNativeMetrics(metrics) {
  const frame = document.querySelector("#platform-frame");
  if (!frame?.contentWindow || !metrics) return;
  const origin = currentFrontendMode === "development" ? new URL(FRONTEND_URL).origin : window.location.origin;
  if (!origin || origin === "null") return;
  try { frame.contentWindow.postMessage({ type: "raventech-native-host-metrics", payload: metrics }, origin); } catch { /* Direct Tauri invocation remains available. */ }
}

function renderCommands() {
  const root = document.querySelector("#commands");
  if (currentNativeRuntime?.runtimeMode === "desktop") { root.replaceChildren(); return; }
  root.replaceChildren(...commands.filter((command) => !command.devOnly || currentFrontendMode === "development").map((command) => {
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
  if (currentNativeRuntime?.runtimeMode === "desktop") {
    if (currentNativeRuntime.postgresql?.state !== "healthy") return "postgresRequiredAction";
    if (currentNativeRuntime.backend?.state === "failed") return currentNativeRuntime.backend.lastError ?? "backendHelpBody";
    if (currentNativeRuntime.worker?.state === "failed") return currentNativeRuntime.worker.lastError ?? "workerHelpBody";
    return currentNativeRuntime.backend?.state === "healthy" && currentNativeRuntime.worker?.state === "running" ? "runtimeReady" : "runtimeStartingAction";
  }
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
  const nativeMode = currentNativeRuntime?.runtimeMode === "desktop";
  const projectReady = nativeMode || snapshot.setup.configuredPathValid;
  const prerequisitesReady = nativeMode ? currentNativeRuntime.postgresql?.state === "healthy" : snapshot.setup.scriptsAvailable && snapshot.dockerAvailability !== "notDetected" && snapshot.backendPortStatus !== "occupied" && (snapshot.frontendMode !== "development" || snapshot.frontendPortStatus !== "occupied");
  const servicesReady = snapshot.backend.healthy && snapshot.readiness.healthy && snapshot.frontend.healthy && snapshot.releaseMatches === true && snapshot.migrationStatus === "ok";
  for (const [step, ready] of [["project", projectReady], ["prerequisites", prerequisitesReady], ["services", servicesReady]]) {
    const item = document.querySelector(`#step-${step}`); item.classList.toggle("complete", ready); item.classList.toggle("attention", !ready);
    setState(document.querySelector(`#step-${step}-state`), copy(ready ? "stepComplete" : "stepNeedsAction"), ready);
  }
}

function stateIsReady(state) { return ["healthy", "running", "ready"].includes(state); }

function paintNativeCheck(id, ready, pending = false) {
  setState(document.querySelector(id), copy(ready ? "nativePass" : pending ? "nativePending" : "nativeFail"), ready);
}

function paintNativeStep(name, ready, pending = false) {
  const item = document.querySelector(`#native-step-${name}`);
  item.classList.toggle("complete", ready);
  item.classList.toggle("attention", !ready && !pending);
  setState(document.querySelector(`#native-state-${name}`), copy(ready ? "nativePass" : pending ? "nativePending" : "nativeFail"), ready);
}

function renderNativeAcceptance(snapshot) {
  const runtime = currentNativeRuntime;
  if (!runtime) return false;
  const databaseReady = stateIsReady(runtime.postgresql?.state);
  const backendReady = stateIsReady(runtime.backend?.state) && snapshot.backend.healthy && snapshot.readiness.healthy;
  const workerReady = stateIsReady(runtime.worker?.state);
  const embeddedReady = runtime.embeddedFrontend === "ready" && snapshot.frontendMode === "embedded" && snapshot.frontend.healthy;
  const monitoringReady = snapshot.nativeHostMetrics?.available === true;
  const migrationsReady = snapshot.migrationStatus === "ok" || runtime.postgresql?.migrationState === "current";
  const jobsReady = snapshot.backgroundJobBackend === "native" && workerReady;
  const releaseReady = snapshot.releaseMatches === true;
  for (const [id, ready, pending] of [
    ["#accept-database", databaseReady, ["waiting", "starting"].includes(runtime.postgresql?.state)],
    ["#accept-backend", backendReady, ["waiting", "starting"].includes(runtime.backend?.state)],
    ["#accept-worker", workerReady, ["waiting", "starting"].includes(runtime.worker?.state)],
    ["#accept-embedded", embeddedReady, !snapshot.frontend],
    ["#accept-monitoring", monitoringReady, !snapshot.nativeHostMetrics],
    ["#accept-migrations", migrationsReady, ["updating", "unknown"].includes(runtime.postgresql?.migrationState)],
    ["#accept-jobs", jobsReady, snapshot.backgroundJobBackend === "unavailable"],
  ]) paintNativeCheck(id, ready, pending);
  paintNativeStep("application", true);
  paintNativeStep("database", databaseReady, ["waiting", "starting"].includes(runtime.postgresql?.state));
  paintNativeStep("backend", backendReady, ["waiting", "starting"].includes(runtime.backend?.state));
  paintNativeStep("worker", workerReady, ["waiting", "starting"].includes(runtime.worker?.state));
  paintNativeStep("monitoring", monitoringReady, !snapshot.nativeHostMetrics);
  const ready = databaseReady && backendReady && workerReady && embeddedReady && monitoringReady && migrationsReady && jobsReady && releaseReady;
  paintNativeStep("ready", ready, !snapshot.backend.reachable || ["waiting", "starting"].includes(runtime.backend?.state));
  return ready;
}

function setDesktopMode(nativeMode) {
  document.querySelector("#setup-panel").hidden = nativeMode;
  document.querySelector("#native-acceptance").hidden = !nativeMode;
  for (const selector of ["#runtime-checklist", "#legacy-launcher-panel", "#legacy-command-result", "#docker-service-card", "#local-endpoints", "#firewall-note"]) {
    document.querySelector(selector).hidden = nativeMode;
  }
  if (nativeMode) setGuidance("");
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
  try { const result = await window.__TAURI__.core.invoke(command.invoke, command.confirmedArgument ? { confirmed: true } : undefined); lastResultKey = !result.scriptAvailable ? "commandUnavailable" : result.timedOut ? "commandTimedOut" : result.success ? "commandSucceeded" : "commandFailed"; if (result.output) { outputNode.textContent = result.output; outputNode.hidden = false; } }
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
  const nativeMode = currentNativeRuntime?.runtimeMode === "desktop";
  setDesktopMode(nativeMode);
  document.querySelector("#hero-title").textContent = copy(nativeMode ? "nativeHeroTitle" : "title");
  document.querySelector("#hero-intro").textContent = copy(nativeMode ? "nativeHeroIntro" : "intro");
  document.querySelector("#open-platform").textContent = copy(nativeMode ? "nativeOpenWorkspace" : "openWorkspace");
  document.querySelector("#native-compatibility").textContent = copy("nativeCompatibility");
  renderSetup(snapshot.setup); renderChecklist(snapshot); renderWizard(snapshot); document.querySelector("#next-action").textContent = copy(nextRuntimeAction(snapshot));
  const nativeAcceptanceReady = nativeMode ? renderNativeAcceptance(snapshot) : false;
  const backendState = !snapshot.backend.reachable ? "unreachable" : snapshot.backend.healthy ? "reachable" : "degraded";
  const readinessState = !snapshot.readiness.reachable ? "unreachable" : snapshot.readiness.healthy ? "ready" : "degraded";
  const frontendState = currentFrontendMode === "embedded" ? "embedded" : !snapshot.frontend.reachable ? "unreachable" : snapshot.frontend.healthy ? "reachable" : "degraded";
  paint("#backend-status", backendState, snapshot.backend.status ?? ""); paint("#ready-status", readinessState, snapshot.readiness.status ?? "");
  setState(document.querySelector("#release-status"), snapshot.releaseVersion ?? copy("unavailable"), snapshot.releaseMatches ?? false);
  document.querySelector("#release-detail").textContent = snapshot.release.httpStatus ? `HTTP ${snapshot.release.httpStatus}` : copy("unknown");
  paint("#frontend-status", frontendState, currentFrontendMode === "embedded" ? copy("bundledAssets") : snapshot.frontend.httpStatus ? `HTTP ${snapshot.frontend.httpStatus}` : "");
  const dockerState = snapshot.dockerServicesStatus ?? (!snapshot.backend.reachable ? "unknown" : "degraded"); paint("#docker-status", dockerState, snapshot.dockerServicesStatus ? copy(dockerState) : copy("unknown"));
  renderHostMetrics(snapshot.nativeHostMetrics); publishNativeMetrics(snapshot.nativeHostMetrics);
  const allReady = nativeMode
    ? nativeAcceptanceReady
    : snapshot.setup.configuredPathValid && snapshot.backend.healthy && snapshot.readiness.healthy && snapshot.frontend.healthy && snapshot.releaseMatches === true && snapshot.migrationStatus === "ok";
  const summary = document.querySelector("#summary"), summaryText = document.querySelector("#summary-text"), openButton = document.querySelector("#open-platform"); openButton.hidden = !allReady;
  if (nativeMode && allReady) { summary.className = "summary success"; summaryText.textContent = copy("nativeReadyMessage"); setGuidance(""); document.querySelector("#hero-title").textContent = copy("nativeReadyTitle"); }
  else if (!nativeMode && !snapshot.setup.configuredPathValid) { summary.className = "summary warning"; summaryText.textContent = copy("setupMessage"); setGuidance(""); }
  else if (!snapshot.backend.reachable) { summary.className = "summary error"; summaryText.textContent = copy(nativeMode ? "nativeBackendMessage" : "backendMessage"); setGuidance(nativeMode ? "" : "backend"); }
  else if (!snapshot.backend.healthy || !snapshot.readiness.healthy) { summary.className = "summary warning"; summaryText.textContent = copy(nativeMode ? "nativeBackendMessage" : "readinessMessage"); setGuidance(nativeMode ? "" : "readiness"); }
  else if (currentFrontendMode === "development" && !snapshot.frontend.healthy) { summary.className = "summary warning"; summaryText.textContent = copy("frontendMessage"); setGuidance("frontend"); }
  else { summary.className = "summary success"; summaryText.textContent = copy("readyMessage"); setGuidance(""); }
  document.querySelector("#platform-summary").textContent = snapshot.releaseVersion ? `${copy("platformHealthy")} · ${snapshot.releaseVersion}` : copy("platformHealthy");
  if (allReady && !previouslyReady && !statusPinned) showPlatform(); if (!allReady && platformOpen) { document.querySelector("#message").textContent = copy("platformDegraded"); showStatus(false); } previouslyReady = allReady;
}

async function refresh() {
  if (checking) return; checking = true; ["#backend-status", "#ready-status", "#release-status", "#frontend-status", "#docker-status"].forEach((id) => paint(id, "checking"));
  try { const [snapshot, runtime] = await Promise.all([window.__TAURI__.core.invoke("probe_local_services"), window.__TAURI__.core.invoke("get_native_runtime_status")]); renderNativeRuntime(runtime); renderSnapshot(snapshot); }
  catch { renderSnapshot({ backend: { reachable: false, healthy: false }, readiness: { reachable: false, healthy: false }, release: { reachable: false, healthy: false }, frontend: { reachable: true, healthy: true, status: "embedded" }, frontendMode: "embedded", releaseVersion: null, dockerServicesStatus: null, dockerAvailability: "notDetected", backendPortStatus: "available", frontendPortStatus: "notRequired", releaseMatches: null, migrationStatus: null, setup: { configured: false, configuredPath: null, configuredPathValid: false, repositoryFound: false, repositoryPath: null, resolutionSource: "copyOnly", composeAvailable: false, frontendAvailable: false, backendAvailable: false, scriptsAvailable: false, nextAction: "bindProjectPath" } }); }
  finally { checking = false; }
}

document.querySelector("#language").addEventListener("click", () => { language = language === "en" ? "es" : "en"; localStorage.setItem("raventech-desktop-language", language); renderLanguage(); refresh(); });
document.querySelector("#refresh").addEventListener("click", refresh); document.querySelector("#show-status").addEventListener("click", () => showStatus(true)); document.querySelector("#open-platform").addEventListener("click", showPlatform);
document.querySelector("#project-form").addEventListener("submit", saveProjectPath); document.querySelector("#clear-project-path").addEventListener("click", clearProjectPath);
document.querySelector("#project-path").addEventListener("input", (event) => event.currentTarget.removeAttribute("aria-invalid"));
document.querySelector("#platform-frame").addEventListener("load", () => { publishNativeMetrics(currentSnapshot?.nativeHostMetrics); publishNativeRuntime(currentNativeRuntime); });
renderLanguage(); refresh(); window.setInterval(refresh, 15_000);
