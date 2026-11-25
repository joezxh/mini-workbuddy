"""临时：复核结论统计 + 15 类约束内关系占比。"""
import psycopg2

from app.config import settings

conn = psycopg2.connect(host=settings.DB_HOST, port=settings.DB_PORT,
                        dbname=settings.DB_NAME, user=settings.DB_USER,
                        password=settings.DB_PASSWORD)
cur = conn.cursor()
cur.execute("select review_verdict, count(*) from kg_triple where knowledge_id=12 "
            "group by review_verdict order by 2 desc")
for r in cur.fetchall():
    print("verdict:", r)

cur.execute("select count(*) from kg_triple where knowledge_id=12")
total = cur.fetchone()[0]
cur.execute("select count(*) from kg_triple where knowledge_id=12 and relation_code in "
            "('生产','供应','提供','库存','存储','签约','采购','配套','代理','协作',"
            "'隶属订单','包含','承运','覆盖','引发风险')")
print(f"15类约束内: {cur.fetchone()[0]} / {total}")

cur.execute("select count(*) from kg_entity where knowledge_id=12")
ents = cur.fetchone()[0]
cur.execute("select count(*) from kg_entity where knowledge_id=12 and type_code in "
            "('部门','供应商','产品','物料','仓库','客户','订单','物流','协议','风险事件')")
print(f"10类约束内实体: {cur.fetchone()[0]} / {ents}")
