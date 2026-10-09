#!/usr/bin/env python3
"""
Run every statement in a .sql file on a SQL warehouse through the Statement Execution API.

Usage:  python3 run_sql.py deploy.sql [--show]      (--show prints result rows, e.g. for verify.sql)
Env:    DATABRICKS_PROFILE (default example-workspace), WAREHOUSE_ID (default 6c8615d2e291c37f)

Statements are split on ';' at end of line, except inside metric-view YAML ($$ ... $$) blocks.
Exits non-zero if any statement fails.
"""

import json
import os
import re
import subprocess
import sys

PROFILE = os.environ.get("DATABRICKS_PROFILE", "example-workspace")
WAREHOUSE = os.environ.get("WAREHOUSE_ID", "6c8615d2e291c37f")


def statements(text):
    text = re.sub(r"(?m)^\s*--.*\n", "", text)
    out, buf, in_yaml = [], [], False
    for line in text.split("\n"):
        buf.append(line)
        in_yaml ^= line.count("$$") % 2 == 1
        if not in_yaml and line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";")
            if stmt:
                out.append(stmt)
            buf = []
    if "\n".join(buf).strip():
        out.append("\n".join(buf).strip())
    return out


def run(stmt):
    body = {"warehouse_id": WAREHOUSE, "statement": stmt, "wait_timeout": "50s"}
    r = subprocess.run(["databricks", "api", "post", "/api/2.0/sql/statements", "--profile", PROFILE,
                        "--json", json.dumps(body)], capture_output=True, text=True)
    return json.loads(r.stdout or "{}")


def main():
    path, show = sys.argv[1], "--show" in sys.argv
    failed = 0
    for s in statements(open(path).read()):
        res = run(s)
        state = res.get("status", {}).get("state")
        head = " ".join(s.split())[:90]
        if state != "SUCCEEDED":
            failed += 1
            print(f"  FAIL  {head}\n        {str((res.get('status') or {}).get('error',{}).get('message') or res)[:300]}")
            continue
        print(f"  ok    {head}")
        if show and res.get("manifest", {}).get("schema", {}).get("columns"):
            cols = [c["name"] for c in res["manifest"]["schema"]["columns"]]
            print("        " + " | ".join(cols))
            for row in (res.get("result", {}).get("data_array") or [])[:12]:
                print("        " + " | ".join("" if v is None else str(v)[:40] for v in row))
    print(f"{path}: {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
