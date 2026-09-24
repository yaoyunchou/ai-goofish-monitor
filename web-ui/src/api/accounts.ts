import { http } from '@/lib/http'

export type AccountChannel = 'goofish' | 'xhs'

export interface AccountItem {
  id?: number
  name: string
  path: string
  channel: AccountChannel
  enabled?: boolean
  state_path?: string
  last_error?: string | null
}

export interface AccountDetail extends AccountItem {
  content: string
}

export async function listAccounts(channel?: AccountChannel): Promise<AccountItem[]> {
  const query = channel ? `?channel=${channel}` : ''
  return await http(`/api/accounts${query}`)
}

export async function getAccount(name: string, channel: AccountChannel = 'goofish'): Promise<AccountDetail> {
  return await http(`/api/accounts/${encodeURIComponent(name)}?channel=${channel}`)
}

export async function createAccount(payload: {
  name: string
  content: string
  channel?: AccountChannel
  enabled?: boolean
}): Promise<AccountDetail> {
  return await http('/api/accounts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function updateAccount(
  name: string,
  content: string,
  channel: AccountChannel = 'goofish',
): Promise<AccountDetail> {
  return await http(`/api/accounts/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, channel }),
  })
}

export async function deleteAccount(name: string, channel: AccountChannel = 'goofish'): Promise<{ message: string }> {
  return await http(`/api/accounts/${encodeURIComponent(name)}?channel=${channel}`, { method: 'DELETE' })
}
