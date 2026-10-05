export type CurrentUser = { id: string; login: string; display_name: string; roles: string[] }
export type ReferenceItem = { id: string; code: string; name: string; is_active: boolean; display_order: number }
export type UserItem = { id: string; login: string; display_name: string; is_active: boolean; roles: string[] }
export type InspectionItem = { id: string; control_type_id: string; inspection_kind_id: string; document_number: string; inspection_date: string; state: 'draft' | 'editing' | 'in_progress'; comment: string | null }
export type ViolationItem = { id: string; inspection_id: string; formulation: string; severity: number; due_date: string | null; elimination_date: string | null; annulled: boolean; status: 'eliminated' | 'not_eliminated' | 'overdue' | null }
export type ScopeItem = { id: string; inspection_id: string; department_id: string; object_id: string; comment: string | null }
export type ViolationTypeItem = { id: string; code: string; name: string; severity: number; is_active: boolean }

export class ApiError extends Error { constructor(message: string, public status: number) { super(message) } }

async function request<T>(path: string, token: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { ...options, headers: { Accept: 'application/json', ...(options?.body ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options?.headers } })
  if (!response.ok) { const body = await response.json().catch(() => null) as { detail?: string } | null; throw new ApiError(body?.detail ?? 'Не удалось выполнить запрос', response.status) }
  return response.json() as Promise<T>
}

export async function login(loginValue: string, password: string): Promise<string> { return (await request<{ access_token: string }>('/auth/login', '', { method: 'POST', body: JSON.stringify({ login: loginValue, password }) })).access_token }

export const api = {
  me: (token: string) => request<CurrentUser>('/auth/me', token),
  references: (token: string, resource: string) => request<ReferenceItem[]>(`/references/${resource}?include_inactive=true`, token),
  users: (token: string) => request<UserItem[]>('/users', token),
  inspections: (token: string) => request<InspectionItem[]>('/inspections', token),
  createInspection: (token: string, payload: { control_type_id: string; inspection_kind_id: string; document_number: string; inspection_date: string; comment?: string }) => request<InspectionItem>('/inspections', token, { method: 'POST', body: JSON.stringify(payload) }),
  updateInspection: (token: string, inspectionId: string, payload: { inspection_kind_id: string; document_number: string; inspection_date: string; comment?: string }) => request<InspectionItem>(`/inspections/${inspectionId}`, token, { method: 'PATCH', body: JSON.stringify(payload) }),
  scopes: (token: string, inspectionId: string) => request<ScopeItem[]>(`/inspections/${inspectionId}/scopes`, token),
  violationTypes: (token: string) => request<ViolationTypeItem[]>('/references/violation-types/items', token),
  createViolation: (token: string, inspectionId: string, payload: { inspection_scope_id: string; formulation: string; violated_requirement: string; violation_type_id: string; due_date?: string; due_date_basis?: string; due_date_source_text?: string; document_received_date?: string }) => request<ViolationItem>(`/inspections/${inspectionId}/violations`, token, { method: 'POST', body: JSON.stringify(payload) }),
  violations: (token: string) => request<ViolationItem[]>('/violations', token),
}
