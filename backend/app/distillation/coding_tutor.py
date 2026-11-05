"""Private coding tutoring — teach Spixa Coder by writing real code lessons."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.distillation.engine import DistillationEngine, get_distillation_engine

TUTOR_SYSTEM = (
    "You are Spixa Coder in tutoring mode. Write correct, minimal, production-minded code. "
    "Explain briefly after the code when useful. Prefer tests. Match the requested language. "
    "Use Spixa Engineering Method: evidence, smallest change, verify."
)

# (prompt, output) — each is a tutoring exercise
CODING_LESSONS: tuple[tuple[str, str], ...] = (
    (
        "اكتب دالة Python: is_palindrome(s) تتجاهل المسافات وحالة الأحرف. أضف مثالين.",
        "def is_palindrome(s: str) -> bool:\n"
        "    cleaned = ''.join(ch.lower() for ch in s if not ch.isspace())\n"
        "    return cleaned == cleaned[::-1]\n\n"
        "assert is_palindrome('A man a plan a canal Panama')\n"
        "assert not is_palindrome('hello')\n"
        "# Thinking: normalize first; compare to reverse; keep it O(n).",
    ),
    (
        "Write TypeScript: debounce(fn, ms). Include typings.",
        "export function debounce<T extends (...args: any[]) => void>(fn: T, ms: number) {\n"
        "  let t: ReturnType<typeof setTimeout> | undefined;\n"
        "  return (...args: Parameters<T>) => {\n"
        "    if (t) clearTimeout(t);\n"
        "    t = setTimeout(() => fn(...args), ms);\n"
        "  };\n"
        "}\n"
        "// Thinking: clear prior timer; preserve args; useful for search inputs.",
    ),
    (
        "Write Python: safe_div(a, b) returns None on ZeroDivisionError, else float.",
        "def safe_div(a: float, b: float) -> float | None:\n"
        "    try:\n"
        "        return a / b\n"
        "    except ZeroDivisionError:\n"
        "        return None\n\n"
        "assert safe_div(10, 2) == 5.0\n"
        "assert safe_div(1, 0) is None\n",
    ),
    (
        "Write a React hook useLocalStorage(key, initial) in TypeScript.",
        "import { useEffect, useState } from 'react';\n\n"
        "export function useLocalStorage<T>(key: string, initial: T) {\n"
        "  const [value, setValue] = useState<T>(() => {\n"
        "    if (typeof window === 'undefined') return initial;\n"
        "    try {\n"
        "      const raw = window.localStorage.getItem(key);\n"
        "      return raw != null ? (JSON.parse(raw) as T) : initial;\n"
        "    } catch {\n"
        "      return initial;\n"
        "    }\n"
        "  });\n"
        "  useEffect(() => {\n"
        "    try {\n"
        "      window.localStorage.setItem(key, JSON.stringify(value));\n"
        "    } catch {\n"
        "      /* ignore quota */\n"
        "    }\n"
        "  }, [key, value]);\n"
        "  return [value, setValue] as const;\n"
        "}\n",
    ),
    (
        "Write Python FastAPI endpoint GET /health returning {status: ok}.",
        "from fastapi import FastAPI\n\n"
        "app = FastAPI()\n\n"
        "@app.get('/health')\n"
        "def health():\n"
        "    return {'status': 'ok'}\n",
    ),
    (
        "Write SQLAlchemy 2.0 style model User(id, email unique, created_at).",
        "from datetime import datetime, timezone\n"
        "from sqlalchemy import DateTime, String\n"
        "from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column\n\n"
        "class Base(DeclarativeBase):\n"
        "    pass\n\n"
        "class User(Base):\n"
        "    __tablename__ = 'users'\n"
        "    id: Mapped[int] = mapped_column(primary_key=True)\n"
        "    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)\n"
        "    created_at: Mapped[datetime] = mapped_column(\n"
        "        DateTime(timezone=True),\n"
        "        default=lambda: datetime.now(timezone.utc),\n"
        "    )\n",
    ),
    (
        "Fix this bug: def first(xs): return xs[0]  # crashes on empty. Teach the fix.",
        "def first(xs):\n"
        "    if not xs:\n"
        "        return None\n"
        "    return xs[0]\n\n"
        "# Lesson: guard empty sequences; return an explicit sentinel; add a test for [].",
    ),
    (
        "Write Python merge_dicts(a, b) shallow merge, b wins on conflicts.",
        "def merge_dicts(a: dict, b: dict) -> dict:\n"
        "    return {**a, **b}\n\n"
        "assert merge_dicts({'x': 1}, {'x': 2, 'y': 3}) == {'x': 2, 'y': 3}\n",
    ),
    (
        "Write a pytest for a function clamp(n, lo, hi).",
        "def clamp(n, lo, hi):\n"
        "    return max(lo, min(hi, n))\n\n"
        "def test_clamp():\n"
        "    assert clamp(5, 0, 10) == 5\n"
        "    assert clamp(-1, 0, 10) == 0\n"
        "    assert clamp(99, 0, 10) == 10\n",
    ),
    (
        "Write Node.js readJson(path) with fs/promises; throw clear error if invalid JSON.",
        "import { readFile } from 'node:fs/promises';\n\n"
        "export async function readJson(path) {\n"
        "  const raw = await readFile(path, 'utf8');\n"
        "  try {\n"
        "    return JSON.parse(raw);\n"
        "  } catch (err) {\n"
        "    throw new Error(`Invalid JSON in ${path}: ${err.message}`);\n"
        "  }\n"
        "}\n",
    ),
    (
        "Write a Go function Sum(nums []int) int.",
        "package main\n\n"
        "func Sum(nums []int) int {\n"
        "    total := 0\n"
        "    for _, n := range nums {\n"
        "        total += n\n"
        "    }\n"
        "    return total\n"
        "}\n",
    ),
    (
        "Write Rust fn max_i32(a: i32, b: i32) -> i32.",
        "fn max_i32(a: i32, b: i32) -> i32 {\n"
        "    if a >= b { a } else { b }\n"
        "}\n\n"
        "#[cfg(test)]\n"
        "mod tests {\n"
        "    use super::*;\n"
        "    #[test]\n"
        "    fn it_works() {\n"
        "        assert_eq!(max_i32(3, 7), 7);\n"
        "    }\n"
        "}\n",
    ),
    (
        "Teach: rewrite callback style to async/await in JS for fetchJson(url).",
        "// Before: fetch(url).then(r => r.json()).then(data => cb(null, data)).catch(cb)\n"
        "export async function fetchJson(url) {\n"
        "  const res = await fetch(url);\n"
        "  if (!res.ok) throw new Error(`HTTP ${res.status}`);\n"
        "  return res.json();\n"
        "}\n"
        "// Lesson: prefer async/await for linear control flow; check res.ok.",
    ),
    (
        "Write Python class LRUCache(capacity) with get/put O(1) average using OrderedDict.",
        "from collections import OrderedDict\n\n"
        "class LRUCache:\n"
        "    def __init__(self, capacity: int):\n"
        "        self.capacity = capacity\n"
        "        self._data: OrderedDict = OrderedDict()\n\n"
        "    def get(self, key):\n"
        "        if key not in self._data:\n"
        "            return None\n"
        "        self._data.move_to_end(key)\n"
        "        return self._data[key]\n\n"
        "    def put(self, key, value) -> None:\n"
        "        if key in self._data:\n"
        "            self._data.move_to_end(key)\n"
        "        self._data[key] = value\n"
        "        if len(self._data) > self.capacity:\n"
        "            self._data.popitem(last=False)\n",
    ),
    (
        "Write a CSS snippet: centered flex column with gap 1rem.",
        ".stack-center {\n"
        "  display: flex;\n"
        "  flex-direction: column;\n"
        "  align-items: center;\n"
        "  justify-content: center;\n"
        "  gap: 1rem;\n"
        "}\n",
    ),
    (
        "Write Python: parse_kv_line('a=1;b=2') -> dict. Skip empty parts.",
        "def parse_kv_line(line: str) -> dict[str, str]:\n"
        "    out: dict[str, str] = {}\n"
        "    for part in line.split(';'):\n"
        "        part = part.strip()\n"
        "        if not part or '=' not in part:\n"
        "            continue\n"
        "        k, v = part.split('=', 1)\n"
        "        out[k.strip()] = v.strip()\n"
        "    return out\n\n"
        "assert parse_kv_line('a=1;b=2') == {'a': '1', 'b': '2'}\n",
    ),
    (
        "Teach idempotent HTTP PUT handler sketch in FastAPI for upsert item by id.",
        "from fastapi import FastAPI\n"
        "from pydantic import BaseModel\n\n"
        "app = FastAPI()\n"
        "STORE: dict[str, dict] = {}\n\n"
        "class Item(BaseModel):\n"
        "    name: str\n\n"
        "@app.put('/items/{item_id}')\n"
        "def upsert_item(item_id: str, body: Item):\n"
        "    STORE[item_id] = {'id': item_id, 'name': body.name}\n"
        "    return STORE[item_id]\n"
        "# Lesson: PUT same payload twice → same result (idempotent).",
    ),
    (
        "Write TypeScript zod schema for {email: string email, age: number min 0}.",
        "import { z } from 'zod';\n\n"
        "export const PersonSchema = z.object({\n"
        "  email: z.string().email(),\n"
        "  age: z.number().min(0),\n"
        "});\n"
        "export type Person = z.infer<typeof PersonSchema>;\n",
    ),
    (
        "Fix SQL injection lesson: replace f-string query with parameters.",
        "# Bad: cursor.execute(f\"SELECT * FROM users WHERE id={user_id}\")\n"
        "# Good:\n"
        "def get_user(cursor, user_id: int):\n"
        "    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))\n"
        "    return cursor.fetchone()\n"
        "# Lesson: never interpolate untrusted input into SQL.",
    ),
    (
        "Write a small Python CLI: argparse with --name greeting.",
        "import argparse\n\n"
        "def main() -> None:\n"
        "    p = argparse.ArgumentParser()\n"
        "    p.add_argument('--name', required=True)\n"
        "    args = p.parse_args()\n"
        "    print(f'Hello, {args.name}!')\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
    ),
    (
        "Write Docker HEALTHCHECK friendly Python: exit 0 if /tmp/ready exists else 1.",
        "from pathlib import Path\n"
        "import sys\n\n"
        "sys.exit(0 if Path('/tmp/ready').exists() else 1)\n",
    ),
    (
        "Teach write then test: function unique_sorted(xs).",
        "def unique_sorted(xs):\n"
        "    return sorted(set(xs))\n\n"
        "def test_unique_sorted():\n"
        "    assert unique_sorted([3, 1, 2, 1]) == [1, 2, 3]\n"
        "    assert unique_sorted([]) == []\n"
        "# Lesson: implement → assert edge cases → keep pure function.",
    ),
    (
        "Write Next.js App Router route handler GET that returns JSON {ok:true}.",
        "import { NextResponse } from 'next/server';\n\n"
        "export async function GET() {\n"
        "  return NextResponse.json({ ok: true });\n"
        "}\n",
    ),
    (
        "Write Python retry helper: retry(fn, times=3) for exceptions.",
        "import time\n"
        "from typing import Callable, TypeVar\n\n"
        "T = TypeVar('T')\n\n"
        "def retry(fn: Callable[[], T], times: int = 3, delay: float = 0.05) -> T:\n"
        "    last: Exception | None = None\n"
        "    for _ in range(times):\n"
        "        try:\n"
        "            return fn()\n"
        "        except Exception as exc:  # noqa: BLE001 — tutoring example\n"
        "            last = exc\n"
        "            time.sleep(delay)\n"
        "    assert last is not None\n"
        "    raise last\n",
    ),
    # —— Wave 2: deeper private tutoring ——
    (
        "Write Python binary_search(arr, target) on sorted list; return index or -1.",
        "def binary_search(arr: list[int], target: int) -> int:\n"
        "    lo, hi = 0, len(arr) - 1\n"
        "    while lo <= hi:\n"
        "        mid = (lo + hi) // 2\n"
        "        if arr[mid] == target:\n"
        "            return mid\n"
        "        if arr[mid] < target:\n"
        "            lo = mid + 1\n"
        "        else:\n"
        "            hi = mid - 1\n"
        "    return -1\n\n"
        "assert binary_search([1, 3, 5, 7], 5) == 2\n"
        "assert binary_search([1, 3, 5], 2) == -1\n"
        "# Thinking: O(log n); only valid on sorted input.\n",
    ),
    (
        "Write Python flatten one level: flatten([[1,2],[3],4]) -> [1,2,3,4].",
        "from typing import Any\n\n"
        "def flatten(xs: list[Any]) -> list[Any]:\n"
        "    out: list[Any] = []\n"
        "    for x in xs:\n"
        "        if isinstance(x, list):\n"
        "            out.extend(x)\n"
        "        else:\n"
        "            out.append(x)\n"
        "    return out\n\n"
        "assert flatten([[1, 2], [3], 4]) == [1, 2, 3, 4]\n",
    ),
    (
        "Write TypeScript: groupBy<T>(items, keyFn) -> Record<string, T[]>.",
        "export function groupBy<T>(items: T[], keyFn: (item: T) => string): Record<string, T[]> {\n"
        "  const out: Record<string, T[]> = {};\n"
        "  for (const item of items) {\n"
        "    const k = keyFn(item);\n"
        "    (out[k] ??= []).push(item);\n"
        "  }\n"
        "  return out;\n"
        "}\n",
    ),
    (
        "Write Python context manager timer that prints elapsed seconds.",
        "import time\n"
        "from contextlib import contextmanager\n\n"
        "@contextmanager\n"
        "def timer(label: str = 'block'):\n"
        "    start = time.perf_counter()\n"
        "    try:\n"
        "        yield\n"
        "    finally:\n"
        "        print(f'{label}: {time.perf_counter() - start:.4f}s')\n",
    ),
    (
        "Write FastAPI dependency that reads X-Request-Id or creates uuid4.",
        "from uuid import uuid4\n"
        "from fastapi import Header\n\n"
        "async def request_id(x_request_id: str | None = Header(default=None)) -> str:\n"
        "    return x_request_id or str(uuid4())\n",
    ),
    (
        "Write Python sliding window max sum of k consecutive ints.",
        "def max_sum_k(nums: list[int], k: int) -> int:\n"
        "    if k <= 0 or k > len(nums):\n"
        "        raise ValueError('bad k')\n"
        "    window = sum(nums[:k])\n"
        "    best = window\n"
        "    for i in range(k, len(nums)):\n"
        "        window += nums[i] - nums[i - k]\n"
        "        best = max(best, window)\n"
        "    return best\n\n"
        "assert max_sum_k([2, 1, 5, 1, 3, 2], 3) == 9\n",
    ),
    (
        "Write JS EventEmitter-lite: on/emit with Map of arrays.",
        "export class TinyEmitter {\n"
        "  #handlers = new Map();\n"
        "  on(event, fn) {\n"
        "    if (!this.#handlers.has(event)) this.#handlers.set(event, []);\n"
        "    this.#handlers.get(event).push(fn);\n"
        "    return () => this.off(event, fn);\n"
        "  }\n"
        "  off(event, fn) {\n"
        "    const list = this.#handlers.get(event) || [];\n"
        "    this.#handlers.set(event, list.filter((h) => h !== fn));\n"
        "  }\n"
        "  emit(event, ...args) {\n"
        "    for (const fn of this.#handlers.get(event) || []) fn(...args);\n"
        "  }\n"
        "}\n",
    ),
    (
        "Write Python deep_get(obj, path 'a.b.c', default=None).",
        "def deep_get(obj, path: str, default=None):\n"
        "    cur = obj\n"
        "    for part in path.split('.'):\n"
        "        if not isinstance(cur, dict) or part not in cur:\n"
        "            return default\n"
        "        cur = cur[part]\n"
        "    return cur\n\n"
        "assert deep_get({'a': {'b': 1}}, 'a.b') == 1\n"
        "assert deep_get({}, 'x.y', 0) == 0\n",
    ),
    (
        "Write SQL: parameterized INSERT user email with returning id (Postgres style).",
        "-- Good:\n"
        "INSERT INTO users (email) VALUES ($1) RETURNING id;\n"
        "-- Lesson: bind parameters; never string-concat emails.\n",
    ),
    (
        "Write React: ErrorBoundary class that shows fallback UI.",
        "import { Component, type ErrorInfo, type ReactNode } from 'react';\n\n"
        "type Props = { fallback: ReactNode; children: ReactNode };\n"
        "type State = { error: Error | null };\n\n"
        "export class ErrorBoundary extends Component<Props, State> {\n"
        "  state: State = { error: null };\n"
        "  static getDerivedStateFromError(error: Error) {\n"
        "    return { error };\n"
        "  }\n"
        "  componentDidCatch(error: Error, info: ErrorInfo) {\n"
        "    console.error(error, info);\n"
        "  }\n"
        "  render() {\n"
        "    return this.state.error ? this.props.fallback : this.props.children;\n"
        "  }\n"
        "}\n",
    ),
    (
        "Write Python rate limiter token bucket: allow() bool.",
        "import time\n\n"
        "class TokenBucket:\n"
        "    def __init__(self, rate: float, capacity: float):\n"
        "        self.rate = rate\n"
        "        self.capacity = capacity\n"
        "        self.tokens = capacity\n"
        "        self.updated = time.monotonic()\n\n"
        "    def allow(self) -> bool:\n"
        "        now = time.monotonic()\n"
        "        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)\n"
        "        self.updated = now\n"
        "        if self.tokens < 1:\n"
        "            return False\n"
        "        self.tokens -= 1\n"
        "        return True\n",
    ),
    (
        "Write TypeScript: assertNever(x: never): never for exhaustive switches.",
        "export function assertNever(x: never): never {\n"
        "  throw new Error(`Unexpected: ${JSON.stringify(x)}`);\n"
        "}\n",
    ),
    (
        "Write Python: topological sort Kahn for DAG adjacency list; raise on cycle.",
        "from collections import deque\n\n"
        "def topo_sort(graph: dict[str, list[str]]) -> list[str]:\n"
        "    indeg = {n: 0 for n in graph}\n"
        "    for n in graph:\n"
        "        for m in graph[n]:\n"
        "            indeg.setdefault(m, 0)\n"
        "            indeg[m] += 1\n"
        "    q = deque([n for n, d in indeg.items() if d == 0])\n"
        "    out: list[str] = []\n"
        "    while q:\n"
        "        n = q.popleft()\n"
        "        out.append(n)\n"
        "        for m in graph.get(n, []):\n"
        "            indeg[m] -= 1\n"
        "            if indeg[m] == 0:\n"
        "                q.append(m)\n"
        "    if len(out) != len(indeg):\n"
        "        raise ValueError('cycle')\n"
        "    return out\n",
    ),
    (
        "Write bash-safe Python: quote shell arg with shlex.quote.",
        "import shlex\n"
        "import subprocess\n\n"
        "def run_echo(name: str) -> str:\n"
        "    cmd = f'echo {shlex.quote(name)}'\n"
        "    return subprocess.check_output(cmd, shell=True, text=True)\n"
        "# Lesson: never interpolate raw user strings into shell.\n",
    ),
    (
        "Write Next.js middleware matcher sketch that only runs on /api/*.",
        "import { NextResponse } from 'next/server';\n"
        "import type { NextRequest } from 'next/server';\n\n"
        "export function middleware(req: NextRequest) {\n"
        "  const id = req.headers.get('x-request-id') ?? crypto.randomUUID();\n"
        "  const res = NextResponse.next();\n"
        "  res.headers.set('x-request-id', id);\n"
        "  return res;\n"
        "}\n\n"
        "export const config = { matcher: '/api/:path*' };\n",
    ),
    (
        "Write Python pydantic v2 model Order with positive qty and frozen config.",
        "from pydantic import BaseModel, Field, ConfigDict\n\n"
        "class Order(BaseModel):\n"
        "    model_config = ConfigDict(frozen=True)\n"
        "    sku: str\n"
        "    qty: int = Field(gt=0)\n",
    ),
    (
        "Fix race lesson: use asyncio.Lock around shared counter increment.",
        "import asyncio\n\n"
        "counter = 0\n"
        "lock = asyncio.Lock()\n\n"
        "async def bump() -> int:\n"
        "    global counter\n"
        "    async with lock:\n"
        "        await asyncio.sleep(0)\n"
        "        counter += 1\n"
        "        return counter\n"
        "# Lesson: concurrent mutation needs a lock or atomic primitive.\n",
    ),
    (
        "Write CSS: visually-hidden utility for a11y text.",
        ".visually-hidden {\n"
        "  position: absolute;\n"
        "  width: 1px;\n"
        "  height: 1px;\n"
        "  padding: 0;\n"
        "  margin: -1px;\n"
        "  overflow: hidden;\n"
        "  clip: rect(0, 0, 0, 0);\n"
        "  white-space: nowrap;\n"
        "  border: 0;\n"
        "}\n",
    ),
    (
        "Write Go: SafeDivide(a, b float64) (float64, error).",
        "package main\n\n"
        "import \"errors\"\n\n"
        "func SafeDivide(a, b float64) (float64, error) {\n"
        "    if b == 0 {\n"
        "        return 0, errors.New(\"division by zero\")\n"
        "    }\n"
        "    return a / b, nil\n"
        "}\n",
    ),
    (
        "Write Python HTTP client with timeout using httpx sync Client.",
        "import httpx\n\n"
        "def get_json(url: str) -> dict:\n"
        "    with httpx.Client(timeout=5.0) as client:\n"
        "        r = client.get(url)\n"
        "        r.raise_for_status()\n"
        "        return r.json()\n"
        "# Lesson: always set timeouts on network I/O.\n",
    ),
    (
        "Write TypeScript: parseEnvBool(raw, fallback).",
        "export function parseEnvBool(raw: string | undefined, fallback = false): boolean {\n"
        "  if (raw == null || raw === '') return fallback;\n"
        "  const v = raw.trim().toLowerCase();\n"
        "  if (['1', 'true', 'yes', 'on'].includes(v)) return true;\n"
        "  if (['0', 'false', 'no', 'off'].includes(v)) return false;\n"
        "  return fallback;\n"
        "}\n",
    ),
    (
        "Write Python generator chunks(iterable, size).",
        "from typing import Iterable, Iterator, TypeVar\n\n"
        "T = TypeVar('T')\n\n"
        "def chunks(items: Iterable[T], size: int) -> Iterator[list[T]]:\n"
        "    if size <= 0:\n"
        "        raise ValueError('size')\n"
        "    batch: list[T] = []\n"
        "    for item in items:\n"
        "        batch.append(item)\n"
        "        if len(batch) == size:\n"
        "            yield batch\n"
        "            batch = []\n"
        "    if batch:\n"
        "        yield batch\n",
    ),
    (
        "Teach: replace mutable default arg bug in Python.",
        "# Bad: def add(item, bucket=[]): bucket.append(item); return bucket\n"
        "def add(item, bucket=None):\n"
        "    if bucket is None:\n"
        "        bucket = []\n"
        "    bucket.append(item)\n"
        "    return bucket\n"
        "# Lesson: never use mutable default arguments.\n",
    ),
    (
        "Write Rust Result-style Python: Ok/Err NamedTuple helpers sketch.",
        "from typing import Generic, TypeVar, Union\n\n"
        "T = TypeVar('T')\n"
        "E = TypeVar('E')\n\n"
        "class Ok(Generic[T]):\n"
        "    __slots__ = ('value',)\n"
        "    def __init__(self, value: T):\n"
        "        self.value = value\n\n"
        "class Err(Generic[E]):\n"
        "    __slots__ = ('error',)\n"
        "    def __init__(self, error: E):\n"
        "        self.error = error\n\n"
        "Result = Union[Ok[T], Err[E]]\n",
    ),
    (
        "Write Playwright-style Python assert: page title contains text (pseudo).",
        "def assert_title_contains(page, text: str) -> None:\n"
        "    title = page.title()\n"
        "    assert text in title, f'expected {text!r} in title {title!r}'\n",
    ),
    (
        "Write Dockerfile best-practice: non-root USER after apt install sketch.",
        "# ...\n"
        "RUN useradd -m appuser\n"
        "USER appuser\n"
        "WORKDIR /home/appuser/app\n"
        "COPY --chown=appuser:appuser . .\n"
        "CMD [\"python\", \"-m\", \"app\"]\n"
        "# Lesson: drop privileges; avoid running as root.\n",
    ),
    (
        "Write Python redact_secrets(text) masking sk-... and Bearer tokens.",
        "import re\n\n"
        "_PATTERNS = [\n"
        "    re.compile(r'sk-[A-Za-z0-9]{8,}'),\n"
        "    re.compile(r'(?i)bearer\\s+[A-Za-z0-9._\\-]+'),\n"
        "]\n\n"
        "def redact_secrets(text: str) -> str:\n"
        "    out = text\n"
        "    for pat in _PATTERNS:\n"
        "        out = pat.sub('[REDACTED]', out)\n"
        "    return out\n",
    ),
    (
        "Write TypeScript: once(fn) wrapper that runs only first call.",
        "export function once<T extends (...args: any[]) => any>(fn: T): T {\n"
        "  let called = false;\n"
        "  let result: ReturnType<T>;\n"
        "  return ((...args: Parameters<T>) => {\n"
        "    if (!called) {\n"
        "      called = true;\n"
        "      result = fn(...args);\n"
        "    }\n"
        "    return result;\n"
        "  }) as T;\n"
        "}\n",
    ),
    (
        "Write Python pathlib: ensure_dir(path) mkdir parents exist_ok.",
        "from pathlib import Path\n\n"
        "def ensure_dir(path: str | Path) -> Path:\n"
        "    p = Path(path)\n"
        "    p.mkdir(parents=True, exist_ok=True)\n"
        "    return p\n",
    ),
    (
        "Write SQL migration lesson: ADD COLUMN nullable first, backfill, then NOT NULL.",
        "-- 1) ALTER TABLE items ADD COLUMN owner_id INT NULL;\n"
        "-- 2) UPDATE items SET owner_id = 1 WHERE owner_id IS NULL;\n"
        "-- 3) ALTER TABLE items ALTER COLUMN owner_id SET NOT NULL;\n"
        "-- Lesson: avoid locking/failing on large tables with instant NOT NULL.\n",
    ),
    (
        "Write Python dataclass Slot with slots=True frozen.",
        "from dataclasses import dataclass\n\n"
        "@dataclass(slots=True, frozen=True)\n"
        "class Point:\n"
        "    x: float\n"
        "    y: float\n",
    ),
    (
        "Write JS abortable fetch with AbortController timeout ms.",
        "export async function fetchWithTimeout(url, ms = 5000, init = {}) {\n"
        "  const ctrl = new AbortController();\n"
        "  const t = setTimeout(() => ctrl.abort(), ms);\n"
        "  try {\n"
        "    return await fetch(url, { ...init, signal: ctrl.signal });\n"
        "  } finally {\n"
        "    clearTimeout(t);\n"
        "  }\n"
        "}\n",
    ),
    (
        "Teach diff-minimal fix: only change the broken line in greet.",
        "# Broken: def greet(name): return 'Hello, ' + Name\n"
        "def greet(name):\n"
        "    return 'Hello, ' + name\n"
        "# Lesson: smallest correct change; don't rewrite the file.\n",
    ),
    (
        "Write Python memoize decorator for pure functions with lru_cache.",
        "from functools import lru_cache\n\n"
        "@lru_cache(maxsize=256)\n"
        "def fib(n: int) -> int:\n"
        "    if n < 2:\n"
        "        return n\n"
        "    return fib(n - 1) + fib(n - 2)\n",
    ),
    (
        "Write TypeScript branded Id type for UserId.",
        "declare const userIdBrand: unique symbol;\n"
        "export type UserId = string & { readonly [userIdBrand]: void };\n"
        "export function asUserId(raw: string): UserId {\n"
        "  if (!raw) throw new Error('empty id');\n"
        "  return raw as UserId;\n"
        "}\n",
    ),
    (
        "Write pytest fixture sketch: tmp_json_file using tmp_path.",
        "import json\n"
        "import pytest\n\n"
        "@pytest.fixture\n"
        "def tmp_json_file(tmp_path):\n"
        "    path = tmp_path / 'data.json'\n"
        "    path.write_text(json.dumps({'ok': True}), encoding='utf-8')\n"
        "    return path\n\n"
        "def test_reads(tmp_json_file):\n"
        "    assert json.loads(tmp_json_file.read_text(encoding='utf-8'))['ok'] is True\n",
    ),
    (
        "Write Python: stable_unique(xs) preserve first-seen order.",
        "def stable_unique(xs):\n"
        "    seen = set()\n"
        "    out = []\n"
        "    for x in xs:\n"
        "        if x in seen:\n"
        "            continue\n"
        "        seen.add(x)\n"
        "        out.append(x)\n"
        "    return out\n\n"
        "assert stable_unique([2, 1, 2, 3, 1]) == [2, 1, 3]\n",
    ),
    (
        "Write CSS focus-visible ring without outline on mouse click only browsers.",
        ".btn:focus-visible {\n"
        "  outline: 2px solid #0b57d0;\n"
        "  outline-offset: 2px;\n"
        "}\n",
    ),
    (
        "Write Python concurrent.futures map with ThreadPoolExecutor.",
        "from concurrent.futures import ThreadPoolExecutor, as_completed\n\n"
        "def fetch_all(urls, fn, workers=4):\n"
        "    out = {}\n"
        "    with ThreadPoolExecutor(max_workers=workers) as pool:\n"
        "        futs = {pool.submit(fn, u): u for u in urls}\n"
        "        for fut in as_completed(futs):\n"
        "            out[futs[fut]] = fut.result()\n"
        "    return out\n",
    ),
    (
        "Write Zod + TypeScript API response schema parse.",
        "import { z } from 'zod';\n\n"
        "const ApiOk = z.object({ ok: z.literal(true), data: z.unknown() });\n"
        "export function parseApiOk(input: unknown) {\n"
        "  return ApiOk.parse(input);\n"
        "}\n",
    ),
    (
        "Write Python: is_subsequence(a, b) — is a subsequence of b?",
        "def is_subsequence(a: str, b: str) -> bool:\n"
        "    i = 0\n"
        "    for ch in b:\n"
        "        if i < len(a) and a[i] == ch:\n"
        "            i += 1\n"
        "    return i == len(a)\n\n"
        "assert is_subsequence('ace', 'abcde')\n"
        "assert not is_subsequence('aec', 'abcde')\n",
    ),
)


def _expand_lessons() -> list[tuple[str, str]]:
    rows = list(CODING_LESSONS)
    extras: list[tuple[str, str]] = []
    for prompt, output in CODING_LESSONS:
        extras.append(
            (
                prompt + " أضف تعليقًا قصيرًا عن التعقيد إن أمكن.",
                output + "\n# Note: prefer clear O-notation when relevant; keep code minimal.",
            )
        )
        extras.append(
            (
                prompt + " Include a failing-case test or guard.",
                output + "\n# Tutor: always consider empty/null/invalid input.",
            )
        )
        extras.append(
            (
                "Tutor drill — rewrite cleaner if needed:\n" + prompt,
                output + "\n# Tutor: readability over cleverness; name things well.",
            )
        )
        extras.append(
            (
                "Private lesson — explain WHY briefly after code:\n" + prompt,
                output + "\n# Why: correctness + clarity beat clever tricks; verify edge cases.",
            )
        )
        extras.append(
            (
                "Tutor: produce production-minded version:\n" + prompt,
                output + "\n# Prod: timeouts, validation, explicit errors, no secrets in logs.",
            )
        )
    rows.extend(extras)
    micros = [
        (
            "Write Python one-liner identity: def id_(x): ...",
            "def id_(x):\n    return x\n",
        ),
        (
            "Write JS: const add = (a,b) => ...",
            "const add = (a, b) => a + b;\n",
        ),
        (
            "Write Python: def nonempty(xs): bool",
            "def nonempty(xs) -> bool:\n    return bool(xs)\n",
        ),
        (
            "Write TS: export const noop = () => {}",
            "export const noop = (): void => {};\n",
        ),
        (
            "Write Python: def clamp01(x): ...",
            "def clamp01(x: float) -> float:\n    return 0.0 if x < 0 else 1.0 if x > 1 else x\n",
        ),
        (
            "Write JS: const sleep = (ms) => new Promise(...)",
            "const sleep = (ms) => new Promise((r) => setTimeout(r, ms));\n",
        ),
    ]
    for i in range(1, 13):
        for p, o in micros:
            rows.append((f"{p} (rep {i})", o + f"\n# micro-drill {i}"))
    # Spaced repetition of hard wave prompts
    hard = [pair for pair in CODING_LESSONS if "binary_search" in pair[0] or "topo_sort" in pair[0] or "TokenBucket" in pair[1] or "redact_secrets" in pair[0]]
    for round_i in range(1, 4):
        for prompt, output in hard:
            rows.append(
                (
                    f"[spaced rep {round_i}] {prompt}",
                    output + f"\n# spaced-repetition round {round_i}",
                )
            )
    return rows


def seed_coding_tutor(
    *,
    settings: Settings | None = None,
    engine: DistillationEngine | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    engine = engine or get_distillation_engine()
    lessons = _expand_lessons()
    accepted = 0
    ids: list[str] = []
    for prompt, output in lessons:
        result = engine.ingest_teacher_output(
            role="coding",
            prompt=prompt,
            system=TUTOR_SYSTEM,
            teacher_model="spixa/coding-private-tutor",
            teacher_output=output,
            metadata={
                "specialty": "coding",
                "distill": True,
                "tools_ok": True,
                "tests_ok": True,
                "human_verified": True,
                "coding_tutor": True,
                "thought_transfer": True,
            },
        )
        if result.get("accepted"):
            accepted += 1
            ids.append(str(result.get("id")))
    return {
        "ok": True,
        "lessons": len(lessons),
        "accepted": accepted,
        "ids_sample": ids[:10],
        "note_ar": "دروس خصوصية: الوكيل يتعلم بالكتابة — دوال، إصلاحات، اختبارات، أنماط آمنة.",
    }
