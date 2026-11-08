#!/usr/bin/env python3
"""Local publication ledger. Browser actions are performed by Codex Computer Use."""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone.utc).isoformat()


def configuration(root):
    return json.loads((root / "config.json").read_text())


def initialize(root, account="your_brand_account"):
    """Create a local configuration without enabling publication or overwriting files."""
    if not re.fullmatch(r"[A-Za-z0-9_.]{1,30}", account):
        raise ValueError("Supply an Instagram handle, not an email address or credential")
    cfg = json.loads((ROOT / "config.example.json").read_text())
    cfg["account"] = account
    cfg["publishing_enabled"] = False
    cfg["production_content_ready"] = False
    root.mkdir(parents=True, exist_ok=True)
    with (root / "config.json").open("x") as file:
        file.write(json.dumps(cfg, indent=2) + "\n")
    return {"account": account, "publishing_enabled": False,
            "production_content_ready": False, "configuration_created": True}


def database(root):
    folder = root / "state"
    folder.mkdir(exist_ok=True)
    db = sqlite3.connect(str(folder / "ledger.sqlite3"), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS posts (
      id TEXT PRIMARY KEY, account TEXT NOT NULL, local_date TEXT NOT NULL,
      slot TEXT NOT NULL, fingerprint TEXT NOT NULL UNIQUE,
      kind TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, evidence TEXT,
      UNIQUE(account, local_date, slot))""")
    db.commit()
    return db


def asset_fingerprint(post):
    digest = hashlib.sha256()
    digest.update(post["account"].encode())
    digest.update(b"\x00")
    digest.update(post["caption"].encode())
    for filename in post["assets"]:
        path = Path(filename)
        with path.open("rb") as f:
            header = f.read(8)
            if not (header.startswith(b"\x89PNG\r\n\x1a\n") or header.startswith(b"\xff\xd8\xff")):
                raise ValueError("This validated adapter accepts PNG or JPEG image files only")
        digest.update(b"\x00")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def enqueue(root, manifest):
    cfg = configuration(root)
    post = json.loads(Path(manifest).read_text())
    if post.get("account") != cfg["account"]:
        raise ValueError("Manifest account does not match configured account")
    if not isinstance(post.get("caption"), str) or not post["caption"].strip():
        raise ValueError("A caption is required")
    if not isinstance(post.get("assets"), list) or len(post["assets"]) != 1:
        raise ValueError("The first validated route supports one image per post")
    post["assets"] = [str((Path(manifest).resolve().parent / p).resolve()) for p in post["assets"]]
    scheduled = datetime.fromisoformat(post["scheduled_at"])
    if scheduled.tzinfo is None:
        raise ValueError("scheduled_at must include a UTC offset")
    day = scheduled.astimezone(ZoneInfo(cfg["timezone"])).date().isoformat()
    if post.get("kind") not in ("technical_test", "production"):
        raise ValueError("Unknown post kind")
    if post["kind"] == "production" and post.get("ready") is not True:
        raise ValueError("Production manifest must explicitly have ready=true")
    if post["kind"] == "production" and not cfg["production_content_ready"]:
        raise ValueError("Formal brand assets/rules are not ready")
    fingerprint = asset_fingerprint(post)
    with database(root) as db:
        db.execute("BEGIN IMMEDIATE")
        if post["kind"] == "technical_test" and db.execute(
            "SELECT 1 FROM posts WHERE account=? AND kind='technical_test'", (cfg["account"],)
        ).fetchone():
            raise ValueError("The one-time technical test already exists")
        identifier = uuid.uuid4().hex[:16]
        stamp = now()
        db.execute("INSERT INTO posts VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            identifier, cfg["account"], day, post.get("slot", "daily"), fingerprint,
            post["kind"], "READY", json.dumps(post), stamp, stamp, None))
    return {"id": identifier, "status": "READY", "local_date": day, "fingerprint": fingerprint}


def get_post(db, identifier):
    row = db.execute("SELECT * FROM posts WHERE id=?", (identifier,)).fetchone()
    if row is None:
        raise ValueError("Unknown post")
    return row


def validate_gate(root, row, expected_status):
    cfg = configuration(root)
    if not cfg["publishing_enabled"]:
        raise ValueError("Publishing is paused")
    if row["account"] != cfg["account"]:
        raise ValueError("Account mismatch")
    if row["status"] != expected_status:
        raise ValueError("Post is not in the required state; reconcile uncertain outcomes before retrying")
    post = json.loads(row["payload"])
    if post["kind"] == "production" and not cfg["production_content_ready"]:
        raise ValueError("Production content is not ready")
    if asset_fingerprint(post) != row["fingerprint"]:
        raise ValueError("Media or caption changed after queueing")
    if datetime.fromisoformat(post["scheduled_at"]) > datetime.now(timezone.utc):
        raise ValueError("Post is not due yet")
    if row["local_date"] != datetime.now(ZoneInfo(cfg["timezone"])).date().isoformat():
        raise ValueError("Expired daily job; do not publish old queued content automatically")
    return cfg, post


def claim(root, identifier):
    with database(root) as db:
        db.execute("BEGIN IMMEDIATE")
        row = get_post(db, identifier)
        cfg, post = validate_gate(root, row, "READY")
        day = datetime.now(ZoneInfo(cfg["timezone"])).date().isoformat()
        if row["local_date"] != day:
            raise ValueError("Expired daily job; do not publish old queued content automatically")
        active = db.execute("SELECT COUNT(*) FROM posts WHERE account=? AND local_date=? "
                            "AND status IN ('PUBLISHING','VERIFY_REQUIRED','PUBLISHED')", (cfg["account"], day)).fetchone()[0]
        if active >= cfg["daily_limit"]:
            raise ValueError("Daily limit reached or an earlier publication needs reconciliation")
        db.execute("UPDATE posts SET status='PUBLISHING', updated_at=? WHERE id=?", (now(), identifier))
    return {"id": identifier, "status": "PUBLISHING", "post": post,
            "instruction": "Inspect the target account in the UI. Run check immediately before clicking Share. Never repeat Share after an uncertain result."}


def check(root, identifier):
    with database(root) as db:
        row = get_post(db, identifier)
        validate_gate(root, row, "PUBLISHING")
    return {"id": identifier, "gate": "PASS"}


def record(root, identifier, evidence_file):
    evidence = json.loads(Path(evidence_file).read_text())
    parsed = urlparse(evidence.get("url", ""))
    parts = [x for x in parsed.path.split("/") if x]
    if (parsed.scheme != "https" or parsed.netloc not in ("instagram.com", "www.instagram.com")
            or parsed.query or parsed.fragment or len(parts) != 2 or parts[0] not in ("p", "reel")
            or not re.fullmatch(r"[A-Za-z0-9_-]+", parts[1])):
        raise ValueError("An actual Instagram post permalink is required")
    if evidence.get("verified_account") != configuration(root)["account"]:
        raise ValueError("Evidence account mismatch")
    if (evidence.get("publication_success_observed") is not True
            or evidence.get("permalink_reopened_and_verified") is not True):
        raise ValueError("Both the publication result and reopened post must be verified")
    with database(root) as db:
        db.execute("BEGIN IMMEDIATE")
        row = get_post(db, identifier)
        if row["status"] not in ("PUBLISHING", "VERIFY_REQUIRED"):
            raise ValueError("Cannot record this publication state")
        db.execute("UPDATE posts SET status='PUBLISHED', updated_at=?, evidence=? WHERE id=?",
                   (now(), json.dumps(evidence), identifier))
    return {"id": identifier, "status": "PUBLISHED", "url": evidence["url"]}


def uncertain(root, identifier):
    with database(root) as db:
        row = get_post(db, identifier)
        if row["status"] != "PUBLISHING":
            raise ValueError("Only an in-flight publication can have an uncertain result")
        db.execute("UPDATE posts SET status='VERIFY_REQUIRED',updated_at=? WHERE id=?", (now(), identifier))
    return {"id": identifier, "status": "VERIFY_REQUIRED", "retry_allowed": False}


def status(root):
    cfg = configuration(root)
    with database(root) as db:
        rows = [dict(r) for r in db.execute("SELECT id,account,local_date,kind,status,updated_at,evidence FROM posts ORDER BY created_at")]
    return {"account": cfg["account"], "publishing_enabled": cfg["publishing_enabled"],
            "production_content_ready": cfg["production_content_ready"], "posts": rows}


def tick(root):
    """Prepare one due production job; the scheduled Codex agent executes the browser step."""
    cfg = configuration(root)
    report = {"checked_at": now(), "account": cfg["account"], "browser_action_required": False}
    if not cfg["publishing_enabled"]:
        report["result"] = "paused"
        return report
    if not cfg["production_content_ready"]:
        report["result"] = "waiting_for_formal_brand_content"
        return report
    day = datetime.now(ZoneInfo(cfg["timezone"])).date().isoformat()
    with database(root) as db:
        existing = db.execute("SELECT id,status FROM posts WHERE account=? AND local_date=? "
                              "AND status IN ('PUBLISHING','VERIFY_REQUIRED','PUBLISHED')",
                              (cfg["account"], day)).fetchall()
    if existing:
        report.update(result="already_published_or_needs_reconciliation", posts=[dict(r) for r in existing])
        return report
    with database(root) as db:
        ready = db.execute("SELECT id,payload FROM posts WHERE account=? AND local_date=? AND status='READY' "
                           "AND kind='production' ORDER BY created_at", (cfg["account"], day)).fetchall()
    for row in ready:
        if datetime.fromisoformat(json.loads(row["payload"])["scheduled_at"]) <= datetime.now(timezone.utc):
            report.update(result="due_production_job", post_id=row["id"], browser_action_required=True)
            return report
    issues = []
    for path in sorted((root / "inbox").glob("*.json")):
        try:
            content = json.loads(path.read_text())
            if content.get("ready") is not True or content.get("kind") != "production":
                continue
            due = datetime.fromisoformat(content["scheduled_at"])
            if due.tzinfo is None:
                raise ValueError("scheduled_at requires a timezone offset")
            if due.astimezone(ZoneInfo(cfg["timezone"])).date().isoformat() != day or due > datetime.now(timezone.utc):
                continue
            added = enqueue(root, path)
            report.update(result="due_production_job", post_id=added["id"], browser_action_required=True)
            return report
        except (ValueError, KeyError, OSError, sqlite3.IntegrityError) as exc:
            issues.append({"manifest": path.name, "error": str(exc)})
    report.update(result="no_due_approved_content", issues=issues)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("action", choices=("init", "enqueue", "claim", "check", "record", "uncertain", "status", "pause", "resume", "dry-run", "tick"))
    parser.add_argument("arguments", nargs="*")
    args = parser.parse_args()
    root, action, params = args.root.resolve(), args.action, args.arguments
    if action == "init":
        if len(params) > 1:
            raise ValueError("init accepts at most one Instagram handle")
        result = initialize(root, params[0] if params else "your_brand_account")
    elif action in ("pause", "resume"):
        cfg = configuration(root)
        cfg["publishing_enabled"] = action == "resume"
        temp = root / "config.json.tmp"
        temp.write_text(json.dumps(cfg, indent=2) + "\n")
        os.replace(str(temp), str(root / "config.json"))
        result = {"publishing_enabled": cfg["publishing_enabled"]}
    elif action == "tick":
        result = tick(root)
    elif action in ("status", "dry-run"):
        result = status(root)
        if action == "dry-run":
            result["mode"] = "dry-run: no browser action or publication"
    elif action == "enqueue":
        result = enqueue(root, params[0])
    elif action == "claim":
        result = claim(root, params[0])
    elif action == "check":
        result = check(root, params[0])
    elif action == "uncertain":
        result = uncertain(root, params[0])
    else:
        result = record(root, params[0], params[1])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, sqlite3.IntegrityError, IndexError, KeyError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
