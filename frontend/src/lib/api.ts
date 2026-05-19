import type {
  RegisterRequest,
  RegisterResponse,
  LoginResponse,
  SessionResponse,
  SessionListItem,
  SessionDetail,
  ChatRequest,
  ChatResponse,
  TripResponse,
  TripListResponse,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, ...init } = options;
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (init.body && !(init.body instanceof URLSearchParams)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...init, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }

  return res.json() as Promise<T>;
}

// ---- Auth ----

export function register(data: RegisterRequest) {
  return request<RegisterResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function login(email: string, password: string) {
  const body = new URLSearchParams({ username: email, password });
  return request<LoginResponse>("/auth/login", {
    method: "POST",
    body,
  });
}

export function createSession(userToken: string) {
  return request<SessionResponse>("/auth/session", {
    method: "POST",
    token: userToken,
  });
}

export function listSessions(userToken: string) {
  return request<SessionListItem[]>("/auth/sessions", {
    token: userToken,
  });
}

export function getSession(sessionId: string, userToken: string) {
  return request<SessionDetail>(`/chat/sessions/${sessionId}`, {
    token: userToken,
  });
}

export function deleteSession(sessionId: string, userToken: string) {
  return request<{ status: string }>(`/auth/session/${sessionId}`, {
    method: "DELETE",
    token: userToken,
  });
}

export function renameSession(sessionId: string, name: string, userToken: string) {
  return request<{ status: string }>(`/auth/session/${sessionId}/name`, {
    method: "PATCH",
    token: userToken,
    body: JSON.stringify({ name }),
  });
}

// ---- Chat ----

export function chat(messages: ChatRequest["messages"], sessionToken: string) {
  return request<ChatResponse>("/chat/chat", {
    method: "POST",
    token: sessionToken,
    body: JSON.stringify({ messages }),
  });
}

export function getStreamUrl() {
  return `${BASE_URL}/chat/chat/stream`;
}

// ---- Trip ----

export function listTrips(userToken: string) {
  return request<TripListResponse>("/trip", { token: userToken });
}

export function getTrip(tripId: string, userToken: string) {
  return request<TripResponse>(`/trip/${tripId}`, { token: userToken });
}

export function deleteTrip(tripId: string, userToken: string) {
  return request<{ status: string }>(`/trip/${tripId}`, {
    method: "DELETE",
    token: userToken,
  });
}

export { ApiError };
