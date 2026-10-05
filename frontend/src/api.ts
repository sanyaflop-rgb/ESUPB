export type CurrentUser = {
  id: string
  login: string
  display_name: string
  roles: string[]
}

export type ReferenceItem = {
  id: string
  code: string
  name: string
  is_active: boolean
  display_order: number
}

export type UserItem = {
  id: string
  login: string
  display_name: string
  is_active: boolean
  roles: string[]
}

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message)
  }
}

async function request<T>(path: string, token: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new ApiError(body?.detail ?? 'Не удалось выполнить запрос', response.status)
  }
  return response.json() as Promise<T>
}

export async function login(loginValue: string, password: string): Promise<string> {
  const data = await request<{ access_token: string }>('/auth/login', '', {
    method: 'POST',
    body: JSON.stringify({ login: loginValue, password }),
  })
  return data.access_token
}

export const api = {
  me: (token: string) => request<CurrentUser>('/auth/me', token),
  references: (token: string, resource: string) => request<ReferenceItem[]>(`/references/${resource}?include_inactive=true`, token),
  users: (token: string) => request<UserItem[]>('/users', token),
}
