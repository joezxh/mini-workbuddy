from sqlalchemy import create_engine, text
from app.config import settings
from urllib.parse import quote_plus

pw = quote_plus(settings.DB_PASSWORD)
url = f"postgresql+psycopg2://{settings.DB_USER}:{pw}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
eng = create_engine(url)
doc = "be408093e75d4ab6a9ddd6f12f6e55c9"
with eng.connect() as c:
    print("=== kms_document for this uuid ===")
    for r in c.execute(text(
        "SELECT id, uuid_code, knowledge_id, collection, collection_id, name, status "
        "FROM kms_document WHERE uuid_code=:d"
    ), {"d": doc}):
        print(dict(zip(r._fields, r)))

    print("=== kms_segment for this document_id (all) ===")
    rows = c.execute(text(
        "SELECT collection, document_id, chunk_type, count(*) "
        "FROM kms_segment WHERE document_id=:d GROUP BY collection, document_id, chunk_type"
    ), {"d": doc}).fetchall()
    for r in rows:
        print(r)

    print("=== distinct chunk_type overall ===")
    for r in c.execute(text(
        "SELECT collection, chunk_type, count(*) FROM kms_segment "
        "WHERE collection='kb_3' GROUP BY collection, chunk_type"
    )):
        print(r)

    print("=== any segment with collection kb_3 at all? ===")
    n = c.execute(text("SELECT count(*) FROM kms_segment WHERE collection='kb_3'")).scalar()
    print("kb_3 total segments:", n)
eng.dispose()
