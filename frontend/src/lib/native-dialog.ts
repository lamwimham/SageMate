import { invoke } from '@tauri-apps/api/core'

type DialogOpenResult = string | string[] | null
type DialogOpenOptions = { directory: boolean; multiple: boolean; title?: string }

function isTauriRuntime() {
  return typeof window !== 'undefined' && (
    '__TAURI_INTERNALS__' in window ||
    '__TAURI__' in window
  )
}

export async function pickDirectoryPath(): Promise<string | null> {
  if (!isTauriRuntime()) {
    throw new Error('当前浏览器模式无法打开系统目录窗口，请在桌面端使用，或手动输入目录路径。')
  }

  const options: DialogOpenOptions = {
    directory: true,
    multiple: false,
    title: '选择 SageMate 知识库目录',
  }
  const selected = await invoke<DialogOpenResult>('plugin:dialog|open', { options })

  if (Array.isArray(selected)) {
    return selected[0] ?? null
  }
  return selected
}
