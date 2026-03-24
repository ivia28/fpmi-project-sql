

from __future__ import annotations

import os
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from py_scripts.db import get_pg_conn
from py_scripts.files import find_daily_files, archive_file
from py_scripts import etl
from py_scripts.fraud import build_fraud_report

PROJECT_DIR = Path(__file__).resolve().parent
ARCHIVE_DIR = PROJECT_DIR / "archive"
SQL_CREATE  = PROJECT_DIR / "sql_scripts" / "create_dwh.sql"


def run_sql_file(cur, path: Path) -> None:
    """Выполнить SQL-скрипт (используем для CREATE TABLE, если таблиц ещё нет)."""
    sql = path.read_text(encoding="utf-8")
    cur.execute(sql)


def main() -> None:
    # 1) Загружаем переменные окружения из .env (если файл есть)
    load_dotenv(PROJECT_DIR / ".env", encoding="utf-8")

    # 2) Настраиваем логирование (чтобы было видно, что происходит)
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=log_level, format="%(asctime)s | %(levelname)s | %(message)s")
    log = logging.getLogger("fraud_etl")

    # 3) Подключаемся к DWH (PostgreSQL)
    bank_schema = os.getenv("BANK_SCHEMA", "bank")

    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            # 4) Гарантируем, что таблицы существуют (CREATE IF NOT EXISTS)
            log.info("Ensuring DWH tables exist...")
            run_sql_file(cur, SQL_CREATE)
            conn.commit()

            # 5) Ищем входящие файлы по шаблонам задания:
            #    transactions_DDMMYYYY.txt
            #    terminals_DDMMYYYY.xlsx
            #    passport_blacklist_DDMMYYYY.xlsx
            # (только те, которые ещё не .backup)
            files = find_daily_files(PROJECT_DIR)
            if not files:
                log.info("No new files found. Nothing to do.")
                return

            # 6) Обрабатываем файлы по порядку дат.
            #    В один день может быть 3 файла, поэтому удобнее группировать по дате.
            #    Но для простоты делаем так: читаем файл -> грузим в STG -> мерджим в DWH -> архивируем файл.
            for kind, file_dt, path in files:
                run_dt = datetime.now()
                log.info("Processing %s (%s) from file %s", kind, file_dt.date(), path.name)

                # --- ETL: загрузка в staging и далее в DWH ---
                if kind == "transactions":
                    etl.load_transactions_to_stg(cur, path)
                    etl.merge_transactions_fact(cur)
                    etl.meta_set_last_dt(cur, "transactions", file_dt)

                elif kind == "terminals":
                    etl.load_terminals_to_stg(cur, path)
                    etl.merge_terminals_dim_scd1(cur, run_dt=run_dt)
                    etl.meta_set_last_dt(cur, "terminals", file_dt)

                elif kind == "passport_blacklist":
                    etl.load_passport_blacklist_to_stg(cur, path)
                    etl.merge_passport_blacklist_fact(cur)
                    etl.meta_set_last_dt(cur, "passport_blacklist", file_dt)

                else:
                    log.warning("Unknown file type: %s", kind)

                # фиксируем изменения после каждого файла
                conn.commit()

                # --- обработка файлов: переименовать в .backup и перенести в archive ---
                archived = archive_file(path, ARCHIVE_DIR)
                log.info("Archived: %s", archived.name)

            # 7) После загрузки всех файлов строим отчёт (витрину) накоплением:
            #    каждый запуск добавляет новые строки в REP_FRAUD с новым report_dt.
            report_dt = datetime.now()
            log.info("Building fraud report with report_dt=%s", report_dt)

            build_fraud_report(cur, bank_schema=bank_schema, report_dt=report_dt)
            conn.commit()

            log.info("DONE. Fraud events inserted into dwh.rep_fraud.")


if __name__ == "__main__":
    main()
