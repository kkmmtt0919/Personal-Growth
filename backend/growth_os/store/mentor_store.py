"""导师会话持久化；只维护自有表，不写能力与证据。"""

import json


class MentorStore:
    def __init__(self, connection):
        self.db = connection
        self.db.execute("CREATE TABLE IF NOT EXISTS g_mentor_turns ("
                        "id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, text TEXT NOT NULL,"
                        "status TEXT NOT NULL, response TEXT, context TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        self.db.execute("UPDATE g_mentor_turns SET status='interrupted' WHERE status='running'")
        self.db.commit()

    def get(self, request_id):
        row = self.db.execute("SELECT * FROM g_mentor_turns WHERE id=?", (request_id,)).fetchone()
        return self.view(row) if row else None

    def history(self, goal_id):
        rows = self.db.execute("SELECT * FROM g_mentor_turns WHERE goal_id=? ORDER BY rowid", (goal_id,)).fetchall()
        return [self.view(row) for row in rows]

    def save(self, request_id, goal_id, text, status, *, response=None, context=None):
        self.db.execute("INSERT INTO g_mentor_turns(id,goal_id,text,status,response,context) VALUES(?,?,?,?,?,?) "
                        "ON CONFLICT(id) DO UPDATE SET status=excluded.status,response=excluded.response,context=excluded.context",
                        (request_id, goal_id, text, status, json.dumps(response, ensure_ascii=False),
                         json.dumps(context, ensure_ascii=False)))
        self.db.commit()

    @staticmethod
    def view(row):
        value = dict(row)
        value["response"] = json.loads(value["response"]) if value["response"] else None
        value.pop("context", None)
        return value
