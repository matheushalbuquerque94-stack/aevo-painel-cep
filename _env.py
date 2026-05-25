"""Lookup unificado de variaveis sensiveis.
Ordem de prioridade:
  1. os.environ (Railway, Render, GitHub Actions, Streamlit Cloud via env vars)
  2. arquivo .env (desenvolvimento local)

NOTA: nao usamos st.secrets aqui porque sua chamada ativa o runtime
Streamlit antes do st.set_page_config (causa StreamlitSetPageConfigMustBeFirstCommandError).
No Streamlit Cloud, definir as variaveis no [secrets] mapeia para os.environ tambem,
entao o suporte fica via env vars somente.

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


def get(key, default=None):
    """Le secret de os.environ > .env. Retorna default se nao achar."""
    v = os.environ.get(key)
    if v is not None: return v
    return _read_file().get(key, default)
