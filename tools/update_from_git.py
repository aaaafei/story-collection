# -*- coding: utf-8 -*-
"""核对网页校验密码后，在项目目录执行固定的 git pull --ff-only。

网页传来的密码只和 UPDATE_PASSWORD 比较，用来挡住反复尝试。
它不会写入环境变量，也不会当作 Git 的用户名或密码。
Git 使用服务器上已经配置好的登录。
"""
from __future__ import print_function

import hashlib
import hmac
import os
import re
import subprocess

SECRET_KEYS = (
    "UPDATE_PASSWORD",
    "UPDATE_PASSWORD_SHA256",
    "NOTION_TOKEN",
    "NOTION_API_KEY",
    "NOTION_SECRET",
    "GITEE_TOKEN",
)
TOKEN_RE = re.compile(r"://[^/\s:@]+:[^@\s/]+@")
QUERY_SECRET_RE = re.compile(r"(?i)(token|password|secret|key)=([^&\s]+)")


class UpdateError(Exception):
    def __init__(self, message, status=400):
        super(UpdateError, self).__init__(message)
        self.status = status


def _env_file_values(root):
    found = {}
    for path in (
        os.path.join(root, "tools", ".env"),
        os.path.join(root, ".env"),
    ):
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                found.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return found


def configured_secrets(root):
    """环境变量优先，其次读 tools/.env。每次请求都读文件，改密码不用重启。"""
    file_vals = _env_file_values(root)
    password = (os.environ.get("UPDATE_PASSWORD") or file_vals.get("UPDATE_PASSWORD") or "").strip()
    digest = (
        os.environ.get("UPDATE_PASSWORD_SHA256")
        or file_vals.get("UPDATE_PASSWORD_SHA256")
        or ""
    ).strip().lower()
    return password, digest


def same_secret(given, expected):
    if not given or not expected:
        return False
    left = given.encode("utf-8")
    right = expected.encode("utf-8")
    if len(left) != len(right):
        hmac.compare_digest(left, left)
        return False
    return hmac.compare_digest(left, right)


def password_status(root, given):
    """返回 None 表示还没配置密码；True / False 表示对或不对。"""
    password, digest = configured_secrets(root)
    if not password and not digest:
        return None
    if not isinstance(given, str):
        return False
    given = given.strip()
    if not given or len(given) > 200:
        return False
    ok = False
    if password:
        ok = same_secret(given, password)
    if digest and re.fullmatch(r"[0-9a-f]{64}", digest):
        got = hashlib.sha256(given.encode("utf-8")).hexdigest()
        ok = ok or same_secret(got, digest)
    return ok


def redact(text):
    text = TOKEN_RE.sub("://***@", text or "")
    text = QUERY_SECRET_RE.sub(r"\1=***", text)
    if len(text) > 4000:
        text = text[:4000] + "\n…（输出已截断）"
    return text


def _git_env():
    """沿用服务器自己的 Git 登录，不把网页校验密码带进子进程。"""
    env = os.environ.copy()
    for key in SECRET_KEYS:
        env.pop(key, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    return env


def _run_git(root, args, timeout=120):
    try:
        proc = subprocess.run(
            ["git", "-C", root] + list(args),
            capture_output=True,
            timeout=timeout,
            env=_git_env(),
            check=False,
        )
    except FileNotFoundError:
        raise UpdateError("服务器上找不到 git。请先安装 Git，并确认运行助手的账号能执行 git。", 500)
    except subprocess.TimeoutExpired:
        raise UpdateError("拉取超时。网页里的密码只做校验，Git 使用服务器上已经配置的登录。请到服务器上查看这次拉取。", 504)
    stdout = proc.stdout.decode("utf-8", "replace")
    stderr = proc.stderr.decode("utf-8", "replace")
    return proc.returncode, redact(stdout), redact(stderr)


def _git_text(root, args):
    code, stdout, stderr = _run_git(root, args)
    if code != 0:
        detail = (stderr or stdout or "git 命令失败").strip()
        raise UpdateError(detail, 500)
    return stdout.strip()


def pull_latest(root):
    """只快进当前分支已跟踪的远程分支，不接收网页传来的命令或地址。"""
    code, stdout, stderr = _run_git(root, ["rev-parse", "--is-inside-work-tree"])
    if code != 0 or stdout.strip() != "true":
        raise UpdateError("这个目录还不是 Git 仓库，没法从网页更新。请在服务器的项目目录里先克隆好仓库。", 500)

    code, dirty, dirty_err = _run_git(root, ["status", "--porcelain", "--untracked-files=no"])
    if code != 0:
        raise UpdateError((dirty_err or dirty or "无法查看仓库状态").strip(), 500)
    if dirty.strip():
        raise UpdateError(
            "服务器上的项目有未提交的修改，已停止拉取，避免把这些修改盖掉。",
            409,
        )

    branch = _git_text(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    if branch == "HEAD":
        raise UpdateError("服务器现在不在某个分支上，请先在项目目录检出要更新的分支。", 409)
    upstream_code, upstream, upstream_err = _run_git(
        root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]
    )
    if upstream_code != 0 or not upstream.strip():
        raise UpdateError(
            "当前分支 %s 还没有设置远程跟踪。请在服务器上执行 git branch -u origin/分支名。"
            % branch,
            409,
        )

    before = _git_text(root, ["rev-parse", "--short", "HEAD"])
    code, stdout, stderr = _run_git(root, ["pull", "--ff-only"])
    output = "\n".join(part for part in (stdout, stderr) if part).strip()
    output = output.replace("Already up to date.", "已经是最新。")
    output = output.replace("Fast-forward", "快进更新")
    if code != 0:
        raise UpdateError(output or "拉取失败。", 500)
    after = _git_text(root, ["rev-parse", "--short", "HEAD"])
    names = ""
    if before != after:
        names = _git_text(root, ["diff", "--name-only", before, after])
    restart = any(
        line.startswith("tools/") and line.endswith(".py")
        for line in names.splitlines()
    )
    updated = before != after
    if updated:
        summary = "已更新到 %s（%s）。" % (after, branch)
    else:
        summary = "已经是最新，无需更新。"
    if restart:
        summary += " 助手程序也有改动，请在服务器上重启 python tools/sync_server.py。"
    return {
        "ok": True,
        "updated": updated,
        "restart": restart,
        "branch": branch,
        "upstream": upstream.strip(),
        "before": before,
        "after": after,
        "summary": summary,
        "log": output,
    }
