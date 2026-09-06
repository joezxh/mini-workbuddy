import { getToken } from './auth'

export interface SSEOptions {
  onMessage?: (data: any) => void
  onError?: (error: Event) => void
  onOpen?: () => void
  onClose?: () => void
}

/**
 * 创建 SSE 连接
 */
export function createSSEConnection(url: string, options: SSEOptions = {}) {
  const token = getToken()
  const fullUrl = `${import.meta.env.VITE_API_BASE_URL}${url}?token=${token}`

  const eventSource = new EventSource(fullUrl)

  eventSource.onopen = () => {
    options.onOpen?.()
  }

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      options.onMessage?.(data)
    } catch (error) {
      console.error('SSE 消息解析失败:', error)
    }
  }

  eventSource.onerror = (error) => {
    console.error('SSE 连接错误:', error)
    options.onError?.(error)
    eventSource.close()
  }

  // 返回关闭连接的方法
  return {
    close: () => {
      eventSource.close()
      options.onClose?.()
    }
  }
}

/**
 * 流式请求（用于推演等场景）
 */
export async function streamRequest(
  url: string,
  data: any,
  onChunk: (chunk: string) => void,
  onComplete?: () => void,
  onError?: (error: any) => void
) {
  const token = getToken()
  
  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}${url}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(data)
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) {
      throw new Error('无法获取响应流')
    }

    while (true) {
      const { done, value } = await reader.read()
      
      if (done) {
        onComplete?.()
        break
      }

      const chunk = decoder.decode(value, { stream: true })
      onChunk(chunk)
    }
  } catch (error) {
    console.error('流式请求错误:', error)
    onError?.(error)
  }
}

