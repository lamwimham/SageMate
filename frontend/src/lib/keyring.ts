import { invoke } from '@tauri-apps/api/core'

function isTauriRuntime() {
  return typeof window !== 'undefined' && (
    '__TAURI_INTERNALS__' in window ||
    '__TAURI__' in window
  )
}

export const keyring = {
  isAvailable(): boolean {
    return isTauriRuntime()
  },

  async get(account: string): Promise<string | null> {
    if (!isTauriRuntime()) return null
    return invoke<string | null>('get_credential', {
      service: 'sagemate',
      account,
    }).catch(() => null)
  },

  async set(account: string, password: string): Promise<void> {
    if (!isTauriRuntime()) throw new Error('浏览器模式不支持钥匙串存储')
    await invoke<void>('set_credential', {
      service: 'sagemate',
      account,
      password,
    })
  },

  async del(account: string): Promise<void> {
    if (!isTauriRuntime()) return
    await invoke<void>('delete_credential', {
      service: 'sagemate',
      account,
    }).catch(() => {})
  },
}
