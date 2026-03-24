
CREATE SCHEMA IF NOT EXISTS dwh;


CREATE TABLE IF NOT EXISTS dwh.meta_load (
    entity_name      text PRIMARY KEY,
    last_processed_dt timestamp
);


CREATE TABLE IF NOT EXISTS dwh.stg_transactions (
    transaction_id   varchar(20),
    transaction_date timestamp,
    amount           numeric(18,2),
    card_num         varchar(30),
    oper_type        varchar(20),
    oper_result      varchar(20),
    terminal         varchar(10)
);

CREATE TABLE IF NOT EXISTS dwh.stg_terminals (
    terminal_id      varchar(10),
    terminal_type    varchar(20),
    terminal_city    varchar(100),
    terminal_address varchar(255)
);

CREATE TABLE IF NOT EXISTS dwh.stg_passport_blacklist (
    passport_num varchar(20),
    entry_dt     date
);


CREATE TABLE IF NOT EXISTS dwh.dwh_fact_transactions (
    trans_id     varchar(20) PRIMARY KEY,
    trans_date   timestamp,
    card_num     varchar(30),
    oper_type    varchar(20),
    amt          numeric(18,2),
    oper_result  varchar(20),
    terminal     varchar(10),
    load_dt      timestamp DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dwh.dwh_fact_passport_blacklist (
    passport_num varchar(20),
    entry_dt     date,
    load_dt      timestamp DEFAULT now(),
    PRIMARY KEY (passport_num, entry_dt)
);


CREATE TABLE IF NOT EXISTS dwh.dwh_dim_terminals (
    terminal_id      varchar(10) PRIMARY KEY,
    terminal_type    varchar(20),
    terminal_city    varchar(100),
    terminal_address varchar(255),
    create_dt        timestamp,
    update_dt        timestamp
);


CREATE TABLE IF NOT EXISTS dwh.rep_fraud (
    event_dt   timestamp,
    passport   varchar(20),
    fio        text,
    phone      text,
    event_type text,
    report_dt  timestamp
);

CREATE SCHEMA IF NOT EXISTS bank;

CREATE TABLE IF NOT EXISTS bank.clients (
    client_id          VARCHAR(20) PRIMARY KEY,
    last_name          TEXT,
    first_name         TEXT,
    patronymic         TEXT,
    passport_num       VARCHAR(20),
    passport_valid_to  DATE,
    phone              TEXT
);

CREATE TABLE IF NOT EXISTS bank.accounts (
    account_num VARCHAR(30) PRIMARY KEY,
    valid_to    DATE,
    client      VARCHAR(20) REFERENCES bank.clients(client_id)
);

CREATE TABLE IF NOT EXISTS bank.cards (
    card_num    VARCHAR(30) PRIMARY KEY,
    account_num VARCHAR(30) REFERENCES bank.accounts(account_num)
);