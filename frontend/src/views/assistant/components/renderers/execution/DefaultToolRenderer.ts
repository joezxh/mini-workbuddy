import { h } from 'vue'
import type { ToolCallPair } from '../types/timeline'
import type { ToolRenderer } from './types'
import { toolLabelClass, toolArgClass } from './_shared'

export const DefaultToolRenderer: ToolRenderer = {
  renderHeader(pair: ToolCallPair) {
    return h('div', { class: 'flex items-center gap-x-2' }, [
      h('span', { class: toolLabelClass }, pair.toolName),
      pair.toolDescription
        ? h('span', { class: toolArgClass }, pair.toolDescription)
        : null,
    ])
  },

  renderBody(pair: ToolCallPair) {
    if (!pair.result && pair.status !== 'error') return null
    const children: any[] = []

    // 输入参数
    if (pair.parameters && Object.keys(pair.parameters).length > 0) {
      children.push(h('div', { class: 'execution-body-section' }, [
        h('span', { class: 'execution-body-label' }, '输入参数'),
        h('pre', { class: 'execution-body-code' },
          JSON.stringify(pair.parameters, null, 2)),
      ]))
    }

    // 输出结果或错误
    if (pair.status === 'error' && pair.errorMessage) {
      children.push(h('div', { class: 'execution-body-section execution-body-error' }, [
        h('span', { class: 'execution-body-label' }, '错误'),
        h('pre', { class: 'execution-body-code' }, pair.errorMessage),
      ]))
    } else if (pair.result) {
      children.push(h('div', { class: 'execution-body-section' }, [
        h('span', { class: 'execution-body-label' }, '输出结果'),
        h('pre', { class: 'execution-body-code' },
          JSON.stringify(pair.result, null, 2)),
      ]))
    }

    return h('div', { class: 'execution-body' }, children)
  },
}
