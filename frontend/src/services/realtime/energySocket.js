const listeners = new Set();
const statusListeners = new Set();
let socket = null;
let reconnectTimer = null;
let attempts = 0;
let manuallyStopped = false;

export function getEnergyWebSocketUrl(location, configured = null) {
  if (configured) return configured;
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${location.host}/api/v1/ws/energy`;
}

function websocketUrl() {
  return getEnergyWebSocketUrl(window.location, import.meta.env.VITE_WS_URL);
}

function publishStatus(status) {
  statusListeners.forEach((listener) => listener(status));
}

function scheduleReconnect() {
  if (manuallyStopped || reconnectTimer) return;
  publishStatus("reconnecting");
  const delay = Math.min(1_000 * 2 ** attempts, 15_000);
  attempts += 1;
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    connectEnergySocket();
  }, delay);
}

export function connectEnergySocket() {
  manuallyStopped = false;
  if (socket && [WebSocket.CONNECTING, WebSocket.OPEN].includes(socket.readyState)) return;
  publishStatus(attempts ? "reconnecting" : "connecting");
  socket = new WebSocket(websocketUrl());
  socket.addEventListener("open", () => {
    attempts = 0;
    publishStatus("connected");
    socket.send(JSON.stringify({ type: "ping" }));
  });
  socket.addEventListener("message", (event) => {
    try {
      const message = JSON.parse(event.data);
      listeners.forEach((listener) => listener(message));
      if (message.type === "system.status" && message.data?.heartbeat === "ping") {
        socket?.send(JSON.stringify({ type: "ping" }));
      }
    } catch {
      // Ignore a malformed frame; the next normalized backend event remains usable.
    }
  });
  socket.addEventListener("close", scheduleReconnect);
  socket.addEventListener("error", () => socket?.close());
}

export function subscribeEnergyEvents(listener) {
  listeners.add(listener);
  connectEnergySocket();
  return () => listeners.delete(listener);
}

export function subscribeWithCoalescedRefresh(predicate, refresh, delayMs = 150) {
  let timer = null;
  let inFlight = false;
  let queued = false;
  let disposed = false;
  const run = async () => {
    if (disposed) return;
    if (inFlight) { queued = true; return; }
    inFlight = true;
    try { await refresh(); }
    finally {
      inFlight = false;
      if (queued && !disposed) { queued = false; timer = window.setTimeout(run, delayMs); }
    }
  };
  const unsubscribe = subscribeEnergyEvents((message) => {
    if (!predicate(message)) return;
    if (timer) window.clearTimeout(timer);
    timer = window.setTimeout(run, delayMs);
  });
  return () => {
    disposed = true;
    if (timer) window.clearTimeout(timer);
    unsubscribe();
  };
}

export function subscribeConnectionStatus(listener) {
  statusListeners.add(listener);
  return () => statusListeners.delete(listener);
}

export function stopEnergySocket() {
  manuallyStopped = true;
  if (reconnectTimer) window.clearTimeout(reconnectTimer);
  reconnectTimer = null;
  socket?.close();
  socket = null;
  publishStatus("disconnected");
}
