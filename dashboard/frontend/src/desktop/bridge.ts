type ServiceAction = 'start' | 'stop' | 'restart'
type DesktopPathKind = 'logs' | 'config' | 'workspace' | 'support' | 'clawos'

async function invokeIfAvailable<T>(command: string, payload?: Record<string, unknown>): Promise<T | null> {
  try {
    const mod = await import('@tauri-apps/api/core')
    return await mod.invoke<T>(command, payload)
  } catch {
    return null
  }
}

export const desktopBridge = {
  async isDesktopShell() {
    try {
      const mod = await import('@tauri-apps/api/core')
      return typeof mod.invoke === 'function'
    } catch {
      return false
    }
  },

  async revealLogs() {
    return invokeIfAvailable<string>('reveal_logs')
  },

  async createSupportBundle() {
    return invokeIfAvailable<string>('create_support_bundle')
  },

  async serviceAction(action: ServiceAction, service = 'clawos.service') {
    return invokeIfAvailable<string>('service_action', { action, service })
  },

  async openPath(kind: DesktopPathKind) {
    return invokeIfAvailable<string>('open_path', { kind })
  },
}
