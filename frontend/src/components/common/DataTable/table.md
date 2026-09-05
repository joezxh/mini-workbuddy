#DataTable 组件

## usage

---

DataTable 组件做了自适应高度的处理

```html
  <s-table
    :list='list'
    :pageSize='pageSize'
    :total='total'
    :column='columns'
    :isLoading='isLoading'
    :currentPage='currentPage'
    @on-page-change='fetchList'
    @on-page-size-change='changePageSize'>
    <template slot='filter'>
     <!-- Filter Input -->
    </template>
  </s-table>
```

## props

---

| name          | des                                                         | value-type | default |
| ------------- | ----------------------------------------------------------- | ---------- | ------- |
| list          | 数据源                                                      | `Array`    | `[]`    |
| column        | [项配置]('https://www.iviewui.com/components/table#column') | `Array`    | `[]`    |
| tableColumnsChecked（废除）     | 自定义显示：column中的title集合（只包含需要显示的列）| `Array`  | `[]` |
| isLoading     | 是否暂时加载动画                                            | `Boolean`  | `false` |
| total         | 数据总条数                                                  | `Number`   | `0`     |
| pageSize      | 每页展示条数                                                | `Number`   | `10`    |
| currentPage   | 当前页码                                                    | `Number`   | `1`     |
| filterVisible | 筛选栏是否显示                                              | `Boolean`  | `true`  |
| isMultiple    | 是否开启多选高亮                                              | `Boolean`  | `true`  |
| showTotal    | 显示总数                                              | `Boolean`  | `true`  |

## events

| eventName            | des            | params             |
| -------------------- | -------------- | ------------------ |
| 'on-page-change'     | 切换  页码事件 | `(page) => {}`     |
| 'on-page-size-chang' | 切换展示条数   | `(pageSize) => {}` |
