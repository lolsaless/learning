# -*- coding: utf-8 -*-
"""이력 장부(SQLite 파일 하나). 값이 바뀔 때마다 한 줄씩 '추가만' 한다(지우지 않음)."""
import os
import json
import shutil
import sqlite3
import datetime
import threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS versions(
  ver INTEGER PRIMARY KEY, path TEXT, sha TEXT, created TEXT, note TEXT, user TEXT);
CREATE TABLE IF NOT EXISTS sources(
  sid TEXT PRIMARY KEY, path TEXT, name TEXT, role TEXT, sha TEXT, size INTEGER, mtime REAL,
  added TEXT, active INTEGER DEFAULT 1, last_checked TEXT, status TEXT DEFAULT 'ok');
CREATE TABLE IF NOT EXISTS source_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, sid TEXT, kind TEXT, old_sha TEXT, new_sha TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, ver INTEGER, slot TEXT, label TEXT,
  old TEXT, new TEXT, method TEXT, sid TEXT, source_path TEXT, source_ref TEXT, source_sha TEXT,
  reason TEXT, user TEXT);
CREATE TABLE IF NOT EXISTS confirms(
  slot TEXT PRIMARY KEY, value TEXT, sid TEXT, source_path TEXT, source_ref TEXT, source_sha TEXT,
  ts TEXT, user TEXT);
CREATE TABLE IF NOT EXISTS pending(
  slot TEXT PRIMARY KEY, label TEXT, old TEXT, new TEXT, method TEXT, sid TEXT, source_path TEXT,
  source_ref TEXT, source_sha TEXT, reason TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, ver INTEGER, doc_sha TEXT, summary TEXT);
CREATE TABLE IF NOT EXISTS run_items(
  run_id INTEGER, slot TEXT, label TEXT, value TEXT, status TEXT, fix TEXT, sources TEXT, msg TEXT);
CREATE TABLE IF NOT EXISTS clips(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, path TEXT, sheet TEXT, r0 INTEGER, c0 INTEGER,
  nrows INTEGER, ncols INTEGER, cells TEXT);
"""


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Ledger:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        new = not os.path.exists(path)
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        self.con.commit()
        if new:
            self.set_meta("schema", "1")
            self.set_meta("created", now())

    def close(self):
        with self.lock:
            self.con.close()

    def backup(self, folder, keep=10):
        os.makedirs(folder, exist_ok=True)
        day = datetime.date.today().strftime("%Y-%m-%d")
        dst = os.path.join(folder, f"숫자지기작업_{day}.db")
        if os.path.exists(dst):
            return None
        with self.lock:
            b = sqlite3.connect(dst)
            self.con.backup(b)
            b.close()
        olds = sorted(f for f in os.listdir(folder) if f.startswith("숫자지기작업_") and f.endswith(".db"))
        for f in olds[:-keep]:
            try:
                os.remove(os.path.join(folder, f))
            except OSError:
                pass
        return dst

    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.con.execute(sql, args).fetchall()]

    def x(self, sql, args=()):
        with self.lock:
            cur = self.con.execute(sql, args)
            self.con.commit()
            return cur.lastrowid

    def set_meta(self, k, v):
        self.x("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)))

    def meta(self, k, default=None):
        r = self.q("SELECT value FROM meta WHERE key=?", (k,))
        return r[0]["value"] if r else default

    # 버전
    def add_version(self, ver, path, sha, note, user):
        self.x("INSERT INTO versions(ver,path,sha,created,note,user) VALUES(?,?,?,?,?,?)",
               (ver, path, sha, now(), note, user))

    def versions(self):
        return self.q("SELECT * FROM versions ORDER BY ver")

    def last_version(self):
        r = self.q("SELECT * FROM versions ORDER BY ver DESC LIMIT 1")
        return r[0] if r else None

    def update_version_sha(self, ver, sha):
        self.x("UPDATE versions SET sha=? WHERE ver=?", (sha, ver))

    # 원본
    def next_sid(self):
        r = self.q("SELECT sid FROM sources")
        n = max([int(x["sid"][1:]) for x in r if x["sid"][1:].isdigit()] + [0])
        return f"S{n + 1}"

    def add_source(self, sid, path, name, role, sha, size, mtime):
        self.x("INSERT INTO sources(sid,path,name,role,sha,size,mtime,added,active,last_checked,status) "
               "VALUES(?,?,?,?,?,?,?,?,1,?,'ok')", (sid, path, name, role, sha, size, mtime, now(), now()))
        self.x("INSERT INTO source_events(ts,sid,kind,new_sha,note) VALUES(?,?,?,?,?)", (now(), sid, "등록", sha, path))

    def sources(self, active_only=True):
        if active_only:
            return self.q("SELECT * FROM sources WHERE active=1 ORDER BY CAST(SUBSTR(sid,2) AS INTEGER)")
        return self.q("SELECT * FROM sources ORDER BY CAST(SUBSTR(sid,2) AS INTEGER)")

    def source_by_path(self, path):
        r = self.q("SELECT * FROM sources WHERE path=? AND active=1", (path,))
        return r[0] if r else None

    def deactivate_source(self, sid):
        self.x("UPDATE sources SET active=0 WHERE sid=?", (sid,))
        self.x("INSERT INTO source_events(ts,sid,kind,note) VALUES(?,?,?,?)", (now(), sid, "등록 해제", ""))

    def source_changed(self, sid, old, new, size, mtime, note):
        self.x("UPDATE sources SET sha=?, size=?, mtime=?, last_checked=?, status='ok' WHERE sid=?",
               (new, size, mtime, now(), sid))
        self.x("INSERT INTO source_events(ts,sid,kind,old_sha,new_sha,note) VALUES(?,?,?,?,?,?)",
               (now(), sid, "내용 변경", old, new, note))

    def source_status(self, sid, status):
        self.x("UPDATE sources SET status=?, last_checked=? WHERE sid=?", (status, now(), sid))

    def source_events(self):
        return self.q("SELECT e.*, s.name FROM source_events e LEFT JOIN sources s ON s.sid=e.sid ORDER BY e.id DESC")

    # 값 이력
    def add_event(self, **e):
        cols = ["ts", "ver", "slot", "label", "old", "new", "method", "sid", "source_path", "source_ref",
                "source_sha", "reason", "user"]
        e.setdefault("ts", now())
        self.x(f"INSERT INTO events({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
               tuple(e.get(c) for c in cols))

    def events(self, slot=None, limit=5000):
        if slot:
            return self.q("SELECT * FROM events WHERE slot=? ORDER BY id DESC", (slot,))
        return self.q("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))

    def last_values(self):
        """칸별 마지막으로 기록된 값."""
        out = {}
        for r in self.q("SELECT slot, new FROM events ORDER BY id"):
            out[r["slot"]] = r["new"]
        return out

    # 출처 확정
    def confirm(self, slot, value, sid, path, ref, sha, user):
        self.x("INSERT INTO confirms(slot,value,sid,source_path,source_ref,source_sha,ts,user) VALUES(?,?,?,?,?,?,?,?) "
               "ON CONFLICT(slot) DO UPDATE SET value=excluded.value, sid=excluded.sid, source_path=excluded.source_path, "
               "source_ref=excluded.source_ref, source_sha=excluded.source_sha, ts=excluded.ts, user=excluded.user",
               (slot, value, sid, path, ref, sha, now(), user))

    def unconfirm(self, slot):
        self.x("DELETE FROM confirms WHERE slot=?", (slot,))

    def confirms(self):
        return {r["slot"]: r for r in self.q("SELECT * FROM confirms")}

    # 대기 중 변경
    def set_pending(self, **p):
        cols = ["slot", "label", "old", "new", "method", "sid", "source_path", "source_ref", "source_sha", "reason", "ts"]
        p.setdefault("ts", now())
        self.x(f"INSERT INTO pending({','.join(cols)}) VALUES({','.join('?' * len(cols))}) "
               "ON CONFLICT(slot) DO UPDATE SET " + ",".join(f"{c}=excluded.{c}" for c in cols[1:] if c != "old"),
               tuple(p.get(c) for c in cols))

    def pending(self):
        return self.q("SELECT * FROM pending ORDER BY ts")

    def drop_pending(self, slot=None):
        if slot:
            self.x("DELETE FROM pending WHERE slot=?", (slot,))
        else:
            self.x("DELETE FROM pending")

    # 검증 기록
    def add_run(self, ver, sha, summary, items):
        rid = self.x("INSERT INTO runs(ts,ver,doc_sha,summary) VALUES(?,?,?,?)",
                     (now(), ver, sha, json.dumps(summary, ensure_ascii=False)))
        with self.lock:
            self.con.executemany("INSERT INTO run_items(run_id,slot,label,value,status,fix,sources,msg) VALUES(?,?,?,?,?,?,?,?)",
                                 [(rid,) + tuple(x) for x in items])
            self.con.commit()
        return rid

    def runs(self):
        return self.q("SELECT * FROM runs ORDER BY id DESC")

    # 클립보드
    def add_clip(self, path, sheet, r0, c0, nrows, ncols, cells):
        return self.x("INSERT INTO clips(ts,path,sheet,r0,c0,nrows,ncols,cells) VALUES(?,?,?,?,?,?,?,?)",
                      (now(), path, sheet, r0, c0, nrows, ncols, json.dumps(cells, ensure_ascii=False)))

    def clips(self, limit=500):
        out = []
        for r in self.q("SELECT * FROM clips ORDER BY id DESC LIMIT ?", (limit,)):
            cells = {}
            for k, v in json.loads(r["cells"]).items():
                a, b = k.split(",")
                cells[(int(a), int(b))] = v
            r["cells"] = cells
            r["at"] = r["ts"]
            out.append(r)
        return out
