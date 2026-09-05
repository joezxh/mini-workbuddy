/**
 * SSE Consumer Composable
 * 
 * Manages SSE connection, event streaming, and error handling
 */
import { ref, onUnmounted, type Ref } from 'vue'
import { useSSEStore } from '@/stores/sse'
import type { SSEEvent } from '@/types/sse'

export interface SSEOptions {
  url: string
  signal?: AbortSignal
  onError?: (error: Error) => void
  onDisconnect?: () => void
  enableReconnection?: boolean
  reconnectionDelay?: number
}

export interface UseSSEReturnType {
  isConnected: Ref<boolean>
  isConnecting: Ref<boolean>
  currentUrl: Ref<string | null>
  connect: (options: SSEOptions) => Promise<void>
  disconnect: () => void
  reconnect: () => Promise<void>
  error: Ref<string | null>
}

export function useSSE(): UseSSEReturnType {
  const store = useSSEStore()
  const isConnected = ref(false)
  const isConnecting = ref(false)
  const currentUrl = ref<string | null>(null)
  const error = ref<string | null>(null)
  
  let eventSource: EventSource | null = null
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  
  /**
   * Connect to SSE endpoint
   */
  async function connect(options: SSEOptions): Promise<void> {
    if (isConnected.value || isConnecting.value) return
    
    const { url, signal, onError, onDisconnect } = options
    isConnecting.value = true
    error.value = null
    currentUrl.value = url
    
    try {
      // Create new EventSource with proper headers
      const config = {
        withCredentials: true,
      }
      
      const response = await fetch(url, {
        ...config,
        headers: {
          'Accept': 'text/event-stream',
          'Content-Type': 'application/json',
        },
        signal: signal,
      })
      
      if (!response.ok) {
        throw new Error(`SSE connection failed: ${response.status} ${response.statusText}`)
      }
      
      // Handle successful connection
      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      
      isConnected.value = true
      store.setConnected(true)
      store.clearEvents()
      
      // Read stream in chunks
      while (true) {
        const { done, value } = await reader.read()
        
        if (done) break
        
        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')
        
        for (const line of lines) {
          const parsedEvent = store.parseLine(line.trim())
          
          if (parsedEvent) {
            store.addEvent(parsedEvent as SSEEvent)
            
            // Emit individual events for components
            if (onError && parsedEvent.type === 'error') {
              const errorMsg = (parsedEvent as any).message || 'Unknown error'
              console.error('SSE Error:', errorMsg)
              error.value = errorMsg
            }
          }
        }
      }
      
      // Stream ended normally
      onDisconnect?.()
      disconnect()
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Connection failed'
      error.value = errorMessage
      
      if (onError) {
        onError(err instanceof Error ? err : new Error(errorMessage))
      } else {
        console.error('SSE connection error:', errorMessage)
      }
      
      store.setError(errorMessage)
      store.setConnected(false)
      
      // Attempt reconnection if enabled
      if (options.enableReconnection) {
        scheduleReconnection(options.reconnectionDelay ?? 2000)
      } else {
        disconnect()
      }
    } finally {
      isConnecting.value = false
    }
  }
  
  /**
   * Schedule automatic reconnection
   */
  function scheduleReconnection(delay: number): void {
    if (reconnectTimeout !== null) return
    
    reconnectTimeout = setTimeout(() => {
      reconnectTimeout = null
      connect({
        url: currentUrl.value || '',
        enableReconnection: false, // Prevent infinite loop during scheduled reconnect
      }).catch(console.error)
    }, delay)
  }
  
  /**
   * Force reconnect immediately
   */
  async function reconnect(): Promise<void> {
    if (currentUrl.value) {
      await connect({
        url: currentUrl.value,
        enableReconnection: true,
      })
    }
  }
  
  /**
   * Disconnect and cleanup
   */
  function disconnect(): void {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    
    if (reconnectTimeout !== null) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }
    
    isConnected.value = false
    store.setConnected(false)
  }
  
  // Cleanup on unmount
  onUnmounted(() => {
    disconnect()
  })
  
  return {
    isConnected,
    isConnecting,
    currentUrl,
    connect,
    disconnect,
    reconnect,
    error,
  }
}
