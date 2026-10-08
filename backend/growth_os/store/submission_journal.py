"""交互请求的独立持久化账本，不访问证据数据库。"""

import json
import os
import sqlite3
from pathlib import Path


class SubmissionJournal:
    """独立请求账本；不修改领域表族，完成结果跨进程重开可读。"""

    def __init__(self, path):
        self.lease = Path(str(path) + ".lock").open("a+b")  # noqa: SIM115 -- 持有到服务关闭
        self.lease.seek(0)
        self.lease.write(b"0")
        self.lease.flush()
        self.lease.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lease.close()
            raise RuntimeError("该实验库已有交互服务运行；请使用单进程服务") from None
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS g_submission_requests "
                        "(id TEXT PRIMARY KEY, task TEXT, digest TEXT, status TEXT, result TEXT)")
        self.db.execute("UPDATE g_submission_requests SET status='interrupted' WHERE status='running'")
        self.db.commit()

    def close(self):
        self.db.close()
        self.lease.close()

    def save(self, request_id, task, digest, status, result=None):
        self.db.execute("INSERT OR REPLACE INTO g_submission_requests VALUES(?,?,?,?,?)",
                        (request_id, task, digest, status, json.dumps(result, ensure_ascii=False)))
        self.db.commit()

    def get(self, request_id):
        return self.db.execute("SELECT task,digest,status,result FROM g_submission_requests WHERE id=?",
                               (request_id,)).fetchone()

    def completed_results(self, scope):
        return [json.loads(row[0]) for row in self.db.execute(
            "SELECT result FROM g_submission_requests WHERE task=? AND status='completed' ORDER BY rowid",
            (scope,),
        )]

    def reports(self):
        return {task: json.loads(result)["attribution"] for task, result in self.db.execute(
            "SELECT task,result FROM g_submission_requests WHERE status='completed'")}


    def has_interrupted(self, task_id):
        return self.db.execute(
            "SELECT 1 FROM g_submission_requests WHERE task=? AND status IN ('interrupted','running')",
            (task_id,),
        ).fetchone() is not None
