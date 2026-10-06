export type CurrentUser = { id: string; login: string; display_name: string; roles: string[] }
export type ReferenceItem = { id: string; code: string; name: string; is_active: boolean; display_order: number }
export type UserItem = { id: string; login: string; display_name: string; is_active: boolean; roles: string[] }
export type InspectionItem = { id: string; control_type_id: string; inspection_kind_id: string; department_id: string | null; object_id: string | null; document_number: string; inspection_date: string; state: 'draft' | 'editing' | 'in_progress'; comment: string | null }
export type ObjectItem = { id: string; code: string; name: string; owner_department_id: string | null; is_active: boolean; display_order: number }
export type PersonItem = { id: string; full_name: string; position: string | null; department_id: string | null; is_active: boolean; display_order: number }
export type ViolationTypeItem = { id: string; code: string; name: string; severity: number; is_active: boolean }
export type MeasureItem = { id: string; violation_id: string; department_id: string; object_id: string; person_id: string; elimination_measure: string; due_date: string | null; original_due_date: string | null; elimination_date: string | null; eliminated_during_inspection: boolean; eliminated_late: boolean; days_overdue_at_elimination: number | null; status: 'eliminated' | 'not_eliminated' | 'overdue' }
export type MeasureInput = { department_id: string; object_id: string; person_id: string; elimination_measure: string; due_date?: string }
export type ViolationItem = { id: string; inspection_id: string; formulation: string; violated_requirement: string; severity: number; document_received_date: string | null; annulled: boolean; status: 'eliminated' | 'not_eliminated' | 'overdue' | null; measures: MeasureItem[]; due_date?: string | null; elimination_date?: string | null }

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
  createInspection: (token: string, payload: { control_type_id: string; inspection_kind_id: string; department_id?: string; object_id?: string; document_number: string; inspection_date: string; comment?: string }) => request<InspectionItem>('/inspections', token, { method: 'POST', body: JSON.stringify(payload) }),
  updateInspection: (token: string, inspectionId: string, payload: { inspection_kind_id: string; department_id?: string | null; object_id?: string | null; document_number: string; inspection_date: string; comment?: string }) => request<InspectionItem>(`/inspections/${inspectionId}`, token, { method: 'PATCH', body: JSON.stringify(payload) }),
  objects: (token: string) => request<ObjectItem[]>('/references/objects/items?include_inactive=true', token),
  persons: (token: string) => request<PersonItem[]>('/references/persons/items?include_inactive=true', token),
  violationTypes: (token: string) => request<ViolationTypeItem[]>('/references/violation-types/items', token),
  createViolation: (token: string, inspectionId: string, payload: { formulation: string; violated_requirement: string; violation_type_id: string; document_received_date?: string; measures?: MeasureInput[]; inspection_scope_id?: string; due_date?: string; elimination_measure?: string }) => request<ViolationItem>(`/inspections/${inspectionId}/violations`, token, { method: 'POST', body: JSON.stringify(payload) }),
  violations: (token: string) => request<ViolationItem[]>('/violations', token),
  eliminateMeasure: (token: string, measureId: string, payload: { elimination_date: string; eliminated_during_inspection?: boolean }) => request<MeasureItem>(`/measures/${measureId}/elimination`, token, { method: 'POST', body: JSON.stringify(payload) }),
  changeMeasureDeadline: (token: string, measureId: string, payload: { new_due_date: string; reason: string }) => request(`/measures/${measureId}/deadline-changes`, token, { method: 'POST', body: JSON.stringify(payload) }),
}
