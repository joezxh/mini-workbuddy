export default {
  data() {
    return {
      pageParam: {
        page: 1,
        rows: 10,
        total: 0,
      },
    }
  },
  methods: {
    // 切换每页多少条
    changePageSize(size) {
      this.pageParam.page = 1
      this.pageParam.rows = size
      this.fetchList()
    },
    filterListLeft(page) {
      this.pageParam.page = page
      this.fetchList(page)
    },
  },
}
