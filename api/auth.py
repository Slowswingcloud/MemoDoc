"""用户认证：注册 / 登录 / 令牌（本地 JSON 存储，零第三方依赖）。

角色：user（普通用户）/ admin（管理员）。管理员可查看所有用户、管理所有文件。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

from memodoc.config import settings

USERS_PATH = settings.store_dir / "users.json"
TOKENS_PATH = settings.store_dir / "tokens.json"
TOKEN_TTL = 7 * 24 * 3600  # 7 天


def _hash_password(password: str, salt: str) -> str:
    return hmac.new(salt.encode(), password.encode(), hashlib.sha256).hexdigest()


class AuthService:
    def __init__(self):
        self.users: dict[str, dict] = self._load(USERS_PATH)
        self.tokens: dict[str, dict] = self._load(TOKENS_PATH)  # token -> {username, expiry}

    # ---------- 持久化 ----------
    @staticmethod
    def _load(path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    @staticmethod
    def _save(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- 账号 ----------
    def register(self, username: str, password: str, role: str = "user") -> dict:
        username = username.strip()
        if not (2 <= len(username) <= 20):
            raise ValueError("用户名长度需为 2-20 个字符")
        if not password or len(password) < 6:
            raise ValueError("密码长度至少 6 位")
        if role not in ("user", "admin"):
            raise ValueError("角色只能是 user 或 admin")
        if username in self.users:
            raise ValueError("用户名已存在")
        salt = secrets.token_hex(8)
        self.users[username] = {
            "username": username,
            "salt": salt,
            "password": _hash_password(password, salt),
            "role": role,
            "created_at": time.time(),
        }
        self._save(USERS_PATH, self.users)
        return {"username": username, "role": role}

    def login(self, username: str, password: str) -> dict:
        username = username.strip()
        user = self.users.get(username)
        if not user or user["password"] != _hash_password(password, user["salt"]):
            raise ValueError("用户名或密码错误")
        token = secrets.token_hex(24)
        self.tokens[token] = {"username": username, "expiry": time.time() + TOKEN_TTL}
        self._save(TOKENS_PATH, self.tokens)
        return {"token": token, "username": username, "role": user["role"]}

    def logout(self, token: str) -> None:
        self.tokens.pop(token, None)
        self._save(TOKENS_PATH, self.tokens)

    def get_user(self, token: str) -> dict | None:
        info = self.tokens.get(token)
        if not info:
            return None
        if info["expiry"] < time.time():
            self.tokens.pop(token, None)
            self._save(TOKENS_PATH, self.tokens)
            return None
        user = self.users.get(info["username"])
        if not user:
            return None
        return {"username": user["username"], "role": user["role"]}

    def list_users(self) -> list[dict]:
        return [
            {"username": u["username"], "role": u["role"], "created_at": u.get("created_at", 0)}
            for u in sorted(self.users.values(), key=lambda x: x.get("created_at", 0))
        ]

    def ensure_admin(self) -> None:
        """首次启动时若没有任何账号，创建一个默认管理员 admin/admin123。"""
        if not self.users:
            self.register("admin", "admin123", "admin")


auth = AuthService()
