import { http } from '@/lib/http'

export interface NoteMetrics {
  liked_count: number | null
  collected_count: number | null
  comment_count: number | null
  view_count: number | null
}

export interface XhsNote {
  id: string
  source_url: string
  title: string | null
  author_name: string | null
  last_status: string | null
  last_error: string | null
  snapshot_day: string | null
  metrics: NoteMetrics
  deltas: NoteMetrics
}

export interface NoteAccount {
  id: number
  name: string
  enabled: boolean
}

export interface NoteSchedule {
  cron: string
  enabled: boolean
  account_id: number | null
  next_run_at: string | null
}

export async function listNotes(): Promise<XhsNote[]> {
  const body = await http<{ items: XhsNote[] }>('/api/xhs/notes')
  return body.items
}

export async function addNote(url: string, accountId?: number | null): Promise<XhsNote> {
  return await http('/api/xhs/notes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, account_id: accountId ?? null }),
  })
}

export async function removeNote(noteId: string): Promise<void> {
  await http(`/api/xhs/notes/${encodeURIComponent(noteId)}`, { method: 'DELETE' })
}

export async function collectNotes(noteId?: string): Promise<{ saved: number; failed: number; stopped: boolean; error: string | null }> {
  const path = noteId ? `/api/xhs/notes/${encodeURIComponent(noteId)}/collect` : '/api/xhs/notes/collect'
  return await http(path, { method: 'POST' })
}

export async function listNoteAccounts(): Promise<NoteAccount[]> {
  const body = await http<{ items: NoteAccount[] }>('/api/xhs/notes/accounts')
  return body.items
}

export async function getNoteSchedule(): Promise<NoteSchedule> {
  return await http('/api/xhs/notes/schedule')
}

export async function saveNoteSchedule(cron: string, enabled: boolean, accountId: number | null): Promise<NoteSchedule> {
  return await http('/api/xhs/notes/schedule', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cron, enabled, account_id: accountId }),
  })
}
