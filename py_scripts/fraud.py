from __future__ import annotations
from datetime import datetime

EVENT_PASSPORT = "Совершение операции при просроченном или заблокированном паспорте"
EVENT_CONTRACT = "Совершение операции при недействующем договоре"
EVENT_CITY     = "Совершение операций в разных городах в течение одного часа"
EVENT_AMOUNT   = "Попытка подбора суммы"

def build_fraud_report(cur, bank_schema: str, report_dt: datetime):
    
    cur.execute(f"""        INSERT INTO dwh.rep_fraud (event_dt, passport, fio, phone, event_type, report_dt)
        SELECT t.trans_date,
               c.passport_num,
               (c.last_name || ' ' || c.first_name || ' ' || c.patronymic) AS fio,
               c.phone,
               %s AS event_type,
               %s AS report_dt
        FROM dwh.dwh_fact_transactions t
        JOIN {bank_schema}.cards ca    ON ca.card_num = t.card_num
        JOIN {bank_schema}.accounts a  ON a.account_num = ca.account_num
        JOIN {bank_schema}.clients c   ON c.client_id = a.client
        LEFT JOIN dwh.dwh_fact_passport_blacklist bl
               ON bl.passport_num = c.passport_num AND bl.entry_dt <= t.trans_date::date
        WHERE (c.passport_valid_to < t.trans_date::date OR bl.passport_num IS NOT NULL)
          AND NOT EXISTS (
              SELECT 1 FROM dwh.rep_fraud r
              WHERE r.event_dt = t.trans_date
                AND r.passport = c.passport_num
                AND r.event_type = %s
          );
    """, (EVENT_PASSPORT, report_dt, EVENT_PASSPORT))

    
    cur.execute(f"""        INSERT INTO dwh.rep_fraud (event_dt, passport, fio, phone, event_type, report_dt)
        SELECT t.trans_date,
               c.passport_num,
               (c.last_name || ' ' || c.first_name || ' ' || c.patronymic) AS fio,
               c.phone,
               %s AS event_type,
               %s AS report_dt
        FROM dwh.dwh_fact_transactions t
        JOIN {bank_schema}.cards ca    ON ca.card_num = t.card_num
        JOIN {bank_schema}.accounts a  ON a.account_num = ca.account_num
        JOIN {bank_schema}.clients c   ON c.client_id = a.client
        WHERE a.valid_to < t.trans_date::date
          AND NOT EXISTS (
              SELECT 1 FROM dwh.rep_fraud r
              WHERE r.event_dt = t.trans_date
                AND r.passport = c.passport_num
                AND r.event_type = %s
          );
    """, (EVENT_CONTRACT, report_dt, EVENT_CONTRACT))

    
    cur.execute(f"""        WITH tx AS (
            SELECT t.*,
                   d.terminal_city,
                   lag(d.terminal_city) OVER (PARTITION BY t.card_num ORDER BY t.trans_date) AS prev_city,
                   lag(t.trans_date)    OVER (PARTITION BY t.card_num ORDER BY t.trans_date) AS prev_dt
            FROM dwh.dwh_fact_transactions t
            LEFT JOIN dwh.dwh_dim_terminals d ON d.terminal_id = t.terminal
        ),
        fraud_tx AS (
            SELECT *
            FROM tx
            WHERE prev_city IS NOT NULL
              AND terminal_city IS NOT NULL
              AND terminal_city <> prev_city
              AND trans_date - prev_dt <= interval '1 hour'
        )
        INSERT INTO dwh.rep_fraud (event_dt, passport, fio, phone, event_type, report_dt)
        SELECT f.trans_date,
               c.passport_num,
               (c.last_name || ' ' || c.first_name || ' ' || c.patronymic) AS fio,
               c.phone,
               %s AS event_type,
               %s AS report_dt
        FROM fraud_tx f
        JOIN {bank_schema}.cards ca    ON ca.card_num = f.card_num
        JOIN {bank_schema}.accounts a  ON a.account_num = ca.account_num
        JOIN {bank_schema}.clients c   ON c.client_id = a.client
        WHERE NOT EXISTS (
              SELECT 1 FROM dwh.rep_fraud r
              WHERE r.event_dt = f.trans_date
                AND r.passport = c.passport_num
                AND r.event_type = %s
          );
    """, (EVENT_CITY, report_dt, EVENT_CITY))

    
    cur.execute(f"""        WITH ordered AS (
            SELECT
                t.*,
                row_number() OVER (PARTITION BY t.card_num ORDER BY t.trans_date) AS rn
            FROM dwh.dwh_fact_transactions t
        ),
        w AS (
            SELECT
                o.card_num,
                o.rn,
                o.trans_date AS dt4,
                o.amt        AS a4,
                o.oper_result AS r4,
                lag(o.trans_date,1) OVER (PARTITION BY o.card_num ORDER BY o.rn) AS dt3,
                lag(o.amt,1)        OVER (PARTITION BY o.card_num ORDER BY o.rn) AS a3,
                lag(o.oper_result,1) OVER (PARTITION BY o.card_num ORDER BY o.rn) AS r3,
                lag(o.trans_date,2) OVER (PARTITION BY o.card_num ORDER BY o.rn) AS dt2,
                lag(o.amt,2)        OVER (PARTITION BY o.card_num ORDER BY o.rn) AS a2,
                lag(o.oper_result,2) OVER (PARTITION BY o.card_num ORDER BY o.rn) AS r2,
                lag(o.trans_date,3) OVER (PARTITION BY o.card_num ORDER BY o.rn) AS dt1,
                lag(o.amt,3)        OVER (PARTITION BY o.card_num ORDER BY o.rn) AS a1,
                lag(o.oper_result,3) OVER (PARTITION BY o.card_num ORDER BY o.rn) AS r1
            FROM ordered o
        ),
        fraud_last AS (
            SELECT *
            FROM w
            WHERE r4 = 'SUCCESS'
              AND r1 = 'REJECT' AND r2 = 'REJECT' AND r3 = 'REJECT'
              AND a1 > a2 AND a2 > a3 AND a3 > a4
              AND dt4 - dt1 <= interval '20 minutes'
        )
        INSERT INTO dwh.rep_fraud (event_dt, passport, fio, phone, event_type, report_dt)
        SELECT f.dt4,
               c.passport_num,
               (c.last_name || ' ' || c.first_name || ' ' || c.patronymic) AS fio,
               c.phone,
               %s AS event_type,
               %s AS report_dt
        FROM fraud_last f
        JOIN {bank_schema}.cards ca    ON ca.card_num = f.card_num
        JOIN {bank_schema}.accounts a  ON a.account_num = ca.account_num
        JOIN {bank_schema}.clients c   ON c.client_id = a.client
        WHERE NOT EXISTS (
              SELECT 1 FROM dwh.rep_fraud r
              WHERE r.event_dt = f.dt4
                AND r.passport = c.passport_num
                AND r.event_type = %s
          );
    """, (EVENT_AMOUNT, report_dt, EVENT_AMOUNT))
