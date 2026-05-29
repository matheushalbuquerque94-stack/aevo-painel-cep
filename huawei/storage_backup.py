"""Backup/restore das sessoes Playwright (storage_state) no Supabase.

Uso:
  from huawei.storage_backup import download_storage, upload_storage

  # Antes de abrir cliente: tenta puxar storage do banco
  download_storage("aevomaster", "/tmp/_storage_aevomaster.json", supabase_conn)

  # Depois de fazer login: persiste pro proximo run
  upload_storage("aevomaster", "/tmp/_storage_aevomaster.json", supabase_conn)

Critico para GitHub Actions onde nao ha filesystem persistente entre runs.
"""
import os
import json
from typing import Optional


def download_storage(username: str, dest_path: str, conn) -> bool:
    """Baixa storage_state do Supabase e grava em dest_path.
    Retorna True se baixou com sucesso, False se nao havia (ou erro).
    """
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT storage_state FROM reports.huawei_sessions
                WHERE username=%s AND is_valid=TRUE
            """, (username,))
            row = cur.fetchone()
            if not row or not row[0]: return False
            # storage_state eh JSONB no PG, vem como dict do psycopg2
            data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            with open(dest_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            # Atualiza last_used_at
            cur.execute("""
                UPDATE reports.huawei_sessions
                SET last_used_at=NOW() WHERE username=%s
            """, (username,))
        conn.commit()
        return True
    except Exception as e:
        print(f"  [storage_backup] download falhou p/ {username}: {e}")
        try: conn.rollback()
        except: pass
        return False


def upload_storage(username: str, source_path: str, conn,
                   notes: Optional[str] = None) -> bool:
    """Le source_path e persiste como storage_state no Supabase.
    Marca is_valid=TRUE, reseta failure_count.
    """
    if not os.path.exists(source_path):
        print(f"  [storage_backup] arquivo nao existe: {source_path}")
        return False
    try:
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO reports.huawei_sessions
                    (username, storage_state, last_login_at, last_used_at,
                     is_valid, failure_count, notes)
                VALUES (%s, %s, NOW(), NOW(), TRUE, 0, %s)
                ON CONFLICT (username) DO UPDATE SET
                    storage_state = EXCLUDED.storage_state,
                    last_login_at = NOW(),
                    last_used_at  = NOW(),
                    is_valid      = TRUE,
                    failure_count = 0,
                    notes         = EXCLUDED.notes
            """, (username, json.dumps(data), notes))
        conn.commit()
        return True
    except Exception as e:
        print(f"  [storage_backup] upload falhou p/ {username}: {e}")
        try: conn.rollback()
        except: pass
        return False


def mark_session_invalid(username: str, conn, reason: str = None) -> bool:
    """Marca sessao como invalida (usado pelo health check)."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE reports.huawei_sessions
                SET is_valid=FALSE,
                    failure_count=COALESCE(failure_count,0)+1,
                    notes=%s
                WHERE username=%s
            """, (reason, username))
        conn.commit()
        return True
    except Exception as e:
        print(f"  [storage_backup] mark_invalid falhou: {e}")
        try: conn.rollback()
        except: pass
        return False


def list_sessions(conn) -> list:
    """Lista todas sessoes salvas (sem o storage_state inteiro)."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT username, last_login_at, last_used_at, is_valid,
                       failure_count, notes,
                       LENGTH(storage_state::text) AS size_bytes
                FROM reports.huawei_sessions
                ORDER BY last_used_at DESC NULLS LAST
            """)
            return [{"username": r[0], "last_login_at": r[1], "last_used_at": r[2],
                     "is_valid": r[3], "failure_count": r[4], "notes": r[5],
                     "size_bytes": r[6]} for r in cur.fetchall()]
    except Exception:
        return []
