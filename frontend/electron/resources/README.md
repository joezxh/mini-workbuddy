# 打包资源目录（buildResources）

`electron-builder.yml` 中 `directories.buildResources` 指向此目录。

## 自定义应用图标

把图标文件放到本目录下，并在 `electron-builder.yml` 中取消对应平台 `icon` 的注释：

| 平台 | 文件 | 要求 |
|------|------|------|
| Windows | `icon.ico` | 至少包含 256x256，建议多尺寸 |
| macOS | `icon.icns` | 1024x1024 |
| Linux | `icon.png` | 512x512 |

不提供图标时，electron-builder 会使用 Electron 默认图标，打包不会失败。

可由 `public/brand/logo-icon.svg` 导出上述图标（如 `npx @resvg/resvg-js-cli`、Figma 等）。
