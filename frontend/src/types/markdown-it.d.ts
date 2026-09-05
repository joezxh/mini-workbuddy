declare module 'markdown-it' {
  interface MarkdownItOptions {
    html?: boolean
    linkify?: boolean
    typographer?: boolean
    breaks?: boolean
    highlight?: (code: string, lang: string) => string
  }

  interface Utils {
    escapeHtml: (str: string) => string
  }

  interface RendererRules {
    [key: string]: (tokens: any[], idx: number, options: any, env: any, self: any) => string
  }

  interface Renderer {
    rules: RendererRules
    renderToken(tokens: any[], idx: number, options: any): string
    render(tokens: any[], options: any, env: any): string
  }

  class MarkdownIt {
    constructor(options?: MarkdownItOptions)
    render(src: string): string
    renderer: Renderer
    utils: Utils
  }

  export default MarkdownIt
}