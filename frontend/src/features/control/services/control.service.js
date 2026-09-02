import axiosClient from "../../../services/http/axiosClient";

const requestId = () => crypto.randomUUID();

export async function getControllableBreakers() {
  const { data } = await axiosClient.get("/breakers");
  return data.items || [];
}

export async function switchBreaker(deviceId, state, reason) {
  const { data } = await axiosClient.post(`/breakers/${encodeURIComponent(deviceId)}/switch`, {
    request_id: requestId(), state, confirmed: true, reason,
  });
  return data;
}

export async function setCountdown(deviceId, seconds, reason) {
  const { data } = await axiosClient.put(`/breakers/${encodeURIComponent(deviceId)}/countdown`, {
    request_id: requestId(), seconds, reason: reason || null,
  });
  return data;
}

export async function setRelayRestoreMode(deviceId, mode, reason) {
  const { data } = await axiosClient.put(`/breakers/${encodeURIComponent(deviceId)}/relay-restore-mode`, {
    request_id: requestId(), mode, reason: reason || null,
  });
  return data;
}

export async function setIndicatorMode(deviceId, mode, reason) {
  const { data } = await axiosClient.put(`/breakers/${encodeURIComponent(deviceId)}/indicator-mode`, {
    request_id: requestId(), mode, reason: reason || null,
  });
  return data;
}

export async function setChildLock(deviceId, enabled, reason) {
  const { data } = await axiosClient.put(`/breakers/${encodeURIComponent(deviceId)}/child-lock`, {
    request_id: requestId(), enabled, reason: reason || null,
  });
  return data;
}
