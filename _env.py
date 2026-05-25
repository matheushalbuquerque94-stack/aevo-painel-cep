"""Lookup unificado de variaveis sensiveis.
Ordem de prioridade:
  1. st.secrets (Streamlit Cloud)
  2. os.environ (Railway, GitHub Actions)
  3. arquivo .env (desenvolvimento local)
Uso:
    import _env
    senha = _env.get("SUPABASE_PASSWORD")
"""
import os

_FILE_CACHE = None

def _read_file():
    global _FILE_CACHE
    if _FILE_CACHE is not None: return _FILE_CACHE
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, ".env")
    cache = {}
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1); cache[k.strip()] = v.strip()
    _FILE_CACHE = cache
    return cache


def _try_st_secrets(key):
    try:
        import streamlit as st
        # Streamlit retorna AttributeError se a key nao existir
        return st.secrets[key]
    except Exception:
        return None


def get(key, default=None):
    """Le secret de st.secrets > os.environ > .env. Retorna default se nada."""
    v = _try_st_secrets(key)
    if v is not None: return v
    v = os.environ.get(key)
    if v is not None: return v
    return _read_file().get(key, default)
