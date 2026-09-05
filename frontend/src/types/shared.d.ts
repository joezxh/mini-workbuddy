/**
 * 全局共享类型定义
 */

/** Skill 执行过程中的中间事件（用于可折叠详情面板） */
export interface ExecutionEvent {
  type: 'progress' | 'thinking' | 'tool_call' | 'tool_result' | 'artifact' | 'step'
  time: string
  message: string
  /** 结构化数据（工具参数、执行结果等） */
  data?: Record<string, any>
  /** 思考步骤序号 */
  step?: number
  /** 思考步骤标题 */
  title?: string
  /** step 事件字段（时间线步骤，来自 SSE `type=step` 归一化） */
  phase?: string
  /** 步骤内部事件类型 */
  eventType?: string
  /** 步骤序号（时间线横轴排序用） */
  seq?: number
  /** 步骤状态：done / running / pending */
  status?: string
  /** 步骤详情（可折叠展示） */
  detail?: any
  /** 步骤耗时（毫秒） */
  elapsedMs?: number
}
