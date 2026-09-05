import { ref } from 'vue'

/**
 * 分页 Composable - 适配 Vue 3 Composition API
 * 用法：
 *   const { pageParam, changePageSize, filterListLeft } = usePageMixin(fetchList)
 *
 * @param {(page?: number) => void | Promise<void>} fetchList 列表加载函数
 */
export function usePageMixin(fetchList) {
  const pageParam = ref({
    page: 1,
    rows: 10,
    total: 0,
  })

  function changePageSize(size) {
    pageParam.value.page = 1
    pageParam.value.rows = size
    fetchList && fetchList()
  }

  function filterListLeft(page) {
    pageParam.value.page = page
    fetchList && fetchList(page)
  }

  return {
    pageParam,
    changePageSize,
    filterListLeft,
  }
}

// 兼容旧版 Options API mixin 引用
export default {
  data () {
    return {
      pageParam: {
        page: 1,
        rows: 10,
        total: 0
      }
    }
  },
  methods: {
    // 切换每页多少条
    changePageSize (size) {
      this.pageParam.page = 1
      this.pageParam.rows = size
      this.fetchList()
    },
    filterListLeft (page) {
      this.pageParam.page = page
      this.fetchList(page)
    }
  }
}
