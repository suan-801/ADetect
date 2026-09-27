"""PostgreSQL adapter for the application's small common SQL subset."""
import os
from contextlib import contextmanager


class Row(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)


def row_factory(cursor):
    names=[c.name for c in cursor.description] if cursor.description else []
    return lambda values: Row(zip(names,values))


class Connection:
    def __init__(self,conn): self.conn=conn
    def execute(self,sql,params=()):
        return self.conn.execute(sql.replace('?', '%s'),params)


@contextmanager
def connection(schema):
    import psycopg
    with psycopg.connect(os.environ["ADETECT_DATABASE_URL"],row_factory=row_factory,connect_timeout=10,sslmode="require") as raw:
        conn=Connection(raw)
        for statement in schema.split(';'):
            if statement.strip(): conn.execute(statement)
        conn.execute("ALTER TABLE analysis_session ADD COLUMN IF NOT EXISTS inputs_json TEXT")
        yield conn
