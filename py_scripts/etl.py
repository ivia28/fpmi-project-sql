from __future__ import annotations
from datetime import datetime
from pathlib import Path
import pandas as pd

def _to_amount(x: str) -> float:
    
    return float(str(x).replace(" ", "").replace(",", "."))

def load_transactions_to_stg(cur, file_path: Path):
    df = pd.read_csv(file_path, sep=";")
    df["amount"] = df["amount"].map(_to_amount)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    cur.execute("TRUNCATE TABLE dwh.stg_transactions;")
    args = [tuple(r) for r in df[[
        "transaction_id","transaction_date","amount","card_num","oper_type","oper_result","terminal"
    ]].itertuples(index=False, name=None)]
    cur.executemany(
        """INSERT INTO dwh.stg_transactions
           (transaction_id, transaction_date, amount, card_num, oper_type, oper_result, terminal)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        args
    )

def merge_transactions_fact(cur):
    
    cur.execute("""        INSERT INTO dwh.dwh_fact_transactions (trans_id, trans_date, card_num, oper_type, amt, oper_result, terminal)
        SELECT s.transaction_id, s.transaction_date, s.card_num, s.oper_type, s.amount, s.oper_result, s.terminal
        FROM dwh.stg_transactions s
        LEFT JOIN dwh.dwh_fact_transactions f
          ON f.trans_id = s.transaction_id
        WHERE f.trans_id IS NULL;
    """)

def load_terminals_to_stg(cur, file_path: Path):
    df = pd.read_excel(file_path)
    cur.execute("TRUNCATE TABLE dwh.stg_terminals;")
    args = [tuple(r) for r in df[["terminal_id","terminal_type","terminal_city","terminal_address"]].itertuples(index=False, name=None)]
    cur.executemany(
        """INSERT INTO dwh.stg_terminals
           (terminal_id, terminal_type, terminal_city, terminal_address)
           VALUES (%s,%s,%s,%s)""",
        args
    )

def merge_terminals_dim_scd1(cur, run_dt: datetime):
    
    cur.execute("""        INSERT INTO dwh.dwh_dim_terminals (terminal_id, terminal_type, terminal_city, terminal_address, create_dt, update_dt)
        SELECT s.terminal_id, s.terminal_type, s.terminal_city, s.terminal_address, %s, %s
        FROM dwh.stg_terminals s
        LEFT JOIN dwh.dwh_dim_terminals d
          ON d.terminal_id = s.terminal_id
        WHERE d.terminal_id IS NULL;
    """, (run_dt, run_dt))

    
    cur.execute("""        UPDATE dwh.dwh_dim_terminals d
           SET terminal_type    = s.terminal_type,
               terminal_city    = s.terminal_city,
               terminal_address = s.terminal_address,
               update_dt        = %s
          FROM dwh.stg_terminals s
         WHERE d.terminal_id = s.terminal_id
           AND (
                d.terminal_type    IS DISTINCT FROM s.terminal_type OR
                d.terminal_city    IS DISTINCT FROM s.terminal_city OR
                d.terminal_address IS DISTINCT FROM s.terminal_address
           );
    """, (run_dt,))

def load_passport_blacklist_to_stg(cur, file_path: Path):
    df = pd.read_excel(file_path)
    df["entry_dt"] = pd.to_datetime(df["date"]).dt.date
    df = df.rename(columns={"passport": "passport_num"})[["passport_num","entry_dt"]]
    cur.execute("TRUNCATE TABLE dwh.stg_passport_blacklist;")
    args = [tuple(r) for r in df.itertuples(index=False, name=None)]
    cur.executemany(
        """INSERT INTO dwh.stg_passport_blacklist (passport_num, entry_dt)
           VALUES (%s,%s)""",
        args
    )

def merge_passport_blacklist_fact(cur):
    cur.execute("""        INSERT INTO dwh.dwh_fact_passport_blacklist (passport_num, entry_dt)
        SELECT s.passport_num, s.entry_dt
        FROM dwh.stg_passport_blacklist s
        LEFT JOIN dwh.dwh_fact_passport_blacklist f
          ON f.passport_num = s.passport_num AND f.entry_dt = s.entry_dt
        WHERE f.passport_num IS NULL;
    """)

def meta_get_last_dt(cur, entity: str):
    cur.execute("SELECT last_processed_dt FROM dwh.meta_load WHERE entity_name = %s;", (entity,))
    row = cur.fetchone()
    return row["last_processed_dt"] if row else None

def meta_set_last_dt(cur, entity: str, last_dt: datetime):
    cur.execute("""        INSERT INTO dwh.meta_load (entity_name, last_processed_dt)
        VALUES (%s, %s)
        ON CONFLICT (entity_name) DO UPDATE
           SET last_processed_dt = EXCLUDED.last_processed_dt;
    """, (entity, last_dt))
