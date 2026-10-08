"""用户显式操作的历史；不写证据表或能力等级。"""
import json


class ProductActionStore:
    def __init__(self, connection):
        self.db = connection
        self.db.execute("CREATE TABLE IF NOT EXISTS g_product_actions (id TEXT PRIMARY KEY, kind TEXT NOT NULL, "
                        "goal_id TEXT NOT NULL, payload TEXT NOT NULL, result TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        self.db.commit()

    def get(self, request_id):
        row = self.db.execute("SELECT * FROM g_product_actions WHERE id=?", (request_id,)).fetchone()
        return self.view(row) if row else None

    def history(self, goal_id):
        return [self.view(row) for row in self.db.execute("SELECT * FROM g_product_actions WHERE goal_id=? ORDER BY rowid", (goal_id,))]

    def parent_of(self, goal_id):
        for row in self.db.execute("SELECT * FROM g_product_actions WHERE kind='goal_revision' ORDER BY rowid"):
            value = self.view(row)
            if (value["result"] or {}).get("goal_id") == goal_id:
                return {"goal_id": value["goal_id"], "quote": value["payload"]["text"], "action_id": value["id"]}
        return None

    def save(self, request_id, kind, goal_id, payload, result=None):
        self.db.execute("INSERT INTO g_product_actions(id,kind,goal_id,payload,result) VALUES(?,?,?,?,?) "
                        "ON CONFLICT(id) DO UPDATE SET result=excluded.result",
                        (request_id, kind, goal_id, json.dumps(payload, ensure_ascii=False), json.dumps(result, ensure_ascii=False)))
        self.db.commit()

    @staticmethod
    def view(row):
        value = dict(row)
        for key in ("payload", "result"):
            value[key] = json.loads(value[key]) if value[key] else None
        return value
