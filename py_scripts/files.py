from __future__ import annotations
import re
from pathlib import Path
from datetime import datetime

TX_RE = re.compile(r"^transactions_(\d{8})\.txt$")
TERM_RE = re.compile(r"^terminals_(\d{8})\.xlsx$")
PBL_RE = re.compile(r"^passport_blacklist_(\d{8})\.xlsx$")

def parse_dt_from_filename(ddmmyyyy: str) -> datetime:
    return datetime.strptime(ddmmyyyy, "%d%m%Y")

def find_daily_files(folder: Path):
    
    out = []
    for p in folder.iterdir():
        if p.name.endswith(".backup"):
            continue
        m = TX_RE.match(p.name)
        if m:
            out.append(("transactions", parse_dt_from_filename(m.group(1)), p))
            continue
        m = TERM_RE.match(p.name)
        if m:
            out.append(("terminals", parse_dt_from_filename(m.group(1)), p))
            continue
        m = PBL_RE.match(p.name)
        if m:
            out.append(("passport_blacklist", parse_dt_from_filename(m.group(1)), p))
            continue
    
    out.sort(key=lambda x: (x[1], x[0]))
    return out

def archive_file(path: Path, archive_dir: Path) -> Path:
    archive_dir.mkdir(exist_ok=True)
    backup_name = path.name + ".backup"
    backup_path = path.with_name(backup_name)
    path.rename(backup_path)
    target = archive_dir / backup_name
    if target.exists():
        target.unlink()
    backup_path.rename(target)
    return target
