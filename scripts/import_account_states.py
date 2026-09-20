"""建表 + 导入 state/*.json 到 xianyu_account_states。"""
import os, sys, json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg
from psycopg.rows import dict_row
from src.services.account_state_store import import_all_from_files

url = os.getenv('DATABASE_URL','').replace('postgresql+asyncpg://','postgresql://').replace('postgresql+psycopg://','postgresql://')

migration_sql = (ROOT / "supabase" / "migrations" / "20260806220000_xianyu_account_states.sql").read_text(encoding="utf-8")

with psycopg.connect(url, row_factory=dict_row) as conn:
    conn.execute(migration_sql)
    conn.commit()
    print("[OK] migration 执行完成")

count = import_all_from_files()
print(f"[OK] 导入 {count} 个账号到 xianyu_account_states")

with psycopg.connect(url, row_factory=dict_row) as conn:
    rows = conn.execute("SELECT name, updated_at FROM xianyu_account_states ORDER BY name").fetchall()
    for r in rows:
        print(f"  {r['name']}  updated={r['updated_at']}")
