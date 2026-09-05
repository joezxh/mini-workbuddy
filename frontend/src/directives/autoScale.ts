import type { Directive, DirectiveBinding } from 'vue'

interface AutoScaleOptions {
  width?: number
  height?: number
}

const autoScale: Directive = {
  mounted(el: HTMLElement, { value = {} }: DirectiveBinding<AutoScaleOptions>) {
    const { width = 1920, height = 1080 } = value
    const wrapper = el

    let intervalKey: number | null = null
    let timeoutKey: number | null = null

    intervalKey = window.setInterval(() => {
      if (wrapper.children.length === 0) return
      window.clearInterval(intervalKey!)

      if (wrapper.children.length !== 1) {
        throw new Error('v-auto-scale 指定的标签只能含有一个子节点！')
      }

      const content = wrapper.children[0] as HTMLElement

      const objDom = document.createElement('object')

      const handleObjectLoad = () => {
        objDom.contentDocument?.defaultView?.addEventListener('resize', () => {
          if (timeoutKey) window.clearTimeout(timeoutKey)
          timeoutKey = window.setTimeout(() => {
            const { width: cW, height: cH } = wrapper.getBoundingClientRect()
            content.style.transform = `scaleX(${cW / width}) scaleY(${cH / height})`
          }, 50)
        })

        const { width: cW, height: cH } = wrapper.getBoundingClientRect()
        content.style.transform = `scaleX(${cW / width}) scaleY(${cH / height})`
        content.style.overflow = 'hidden'
        content.style.transformOrigin = '0 0'
        content.style.height = `${height}px`
        content.style.width = `${width}px`

        window.dispatchEvent(new Event('resize'))
      }

      objDom.style.cssText = `
        height: 100%;
        width: 100%;
        overflow: hidden;
        opacity: 0;
        pointer-events: none;
        z-index: -1;
        position: absolute;
        top: 0;
        left: 0;
      `
      objDom.onload = handleObjectLoad
      objDom.type = 'text/html'
      objDom.data = 'about:blank'
      wrapper.appendChild(objDom)
    }, 500)
  }
}

export default autoScale
