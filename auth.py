"""Auth via Supabase reports.users + bcrypt.
Funcoes:
- ensure_login(st): chamada no topo do app; se nao logado, exibe form de login e da st.stop()
- logout(st): limpa sessao
- get_current_user(st): retorna dict do usuario logado ou None

Tambem possui CLI para gerenciar usuarios:
    python auth.py create <username> <email> <nome> [<role>]
    python auth.py list
    python auth.py setpw <username>
    python auth.py disable <username>
"""
import os, sys, getpass

# Conexao Supabase: reusa _sb_connect do app se importado em runtime; CLI usa propria
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import _env as _env_module


def _connect():
    import psycopg2
    host = _env_module.get("SUPABASE_HOST")
    password = _env_module.get("SUPABASE_PASSWORD")
    if not host or not password: return None
    ref = host.split(".")[1]
    region = _env_module.get("SUPABASE_REGION", "us-east-1")
    return psycopg2.connect(
        host=f"aws-1-{region}.pooler.supabase.com", port=5432,
        dbname=_env_module.get("SUPABASE_DB", "postgres"),
        user=f"postgres.{ref}", password=password,
        sslmode="require", connect_timeout=10,
    )


def _hash_pw(pw):
    import bcrypt
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_pw(pw, hashed):
    import bcrypt
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def validate_credentials(username, password):
    """Retorna dict do user se OK, None caso contrario."""
    conn = _connect()
    if conn is None: return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT username, nome, email, password_hash, role, is_active
                FROM reports.users WHERE username=%s
            """, (username,))
            row = cur.fetchone()
            if not row: return None
            uname, nome, email, ph, role, active = row
            if not active: return None
            if not _check_pw(password, ph): return None
            cur.execute("UPDATE reports.users SET last_login=NOW() WHERE username=%s", (username,))
        conn.commit()
        return {"username": uname, "nome": nome, "email": email, "role": role}
    finally:
        conn.close()


def ensure_login(st):
    """Garante usuario logado. Se nao, exibe form e da st.stop()."""
    user = st.session_state.get("auth_user")
    if user: return user

    st.title("AEVO19 — Acesso restrito")
    st.markdown("Sistema de relatorios e painel de portfolio — equipe AEVO")
    with st.form("login_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("Usuario")
        with col2:
            password = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if submit:
        if not username or not password:
            st.error("Preencha usuario e senha.")
        else:
            u = validate_credentials(username.strip(), password)
            if u:
                st.session_state["auth_user"] = u
                st.rerun()
            else:
                st.error("Usuario ou senha invalidos.")
    st.stop()


def logout(st):
    if "auth_user" in st.session_state:
        del st.session_state["auth_user"]
    st.rerun()


def get_current_user(st):
    return st.session_state.get("auth_user")


# ── CLI ─────────────────────────────────────────────────────────────────
def _cli():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    if cmd == "list":
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT username, nome, email, role, is_active, last_login, created_at
                FROM reports.users ORDER BY username
            """)
            rows = cur.fetchall()
        conn.close()
        print(f"\n{'Usuario':<20} {'Nome':<28} {'Role':<8} {'Ativo':<6} {'Last login'}")
        print("-"*90)
        for r in rows:
            uname, nome, email, role, active, last, created = r
            print(f"{uname:<20} {(nome or '')[:28]:<28} {(role or ''):<8} {'sim' if active else 'NAO':<6} {last}")
        print(f"\nTotal: {len(rows)} usuarios")
    elif cmd == "create":
        if len(sys.argv) < 5:
            print("uso: create <username> <email> <nome> [<role>]"); return
        username, email, nome = sys.argv[2], sys.argv[3], sys.argv[4]
        role = sys.argv[5] if len(sys.argv) > 5 else "user"
        pw = getpass.getpass("Senha: ")
        pw2 = getpass.getpass("Confirme: ")
        if pw != pw2: print("Senhas nao batem."); return
        if len(pw) < 6: print("Senha muito curta (min 6)."); return
        ph = _hash_pw(pw)
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO reports.users (username, nome, email, password_hash, role)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE SET
                    nome=EXCLUDED.nome, email=EXCLUDED.email,
                    password_hash=EXCLUDED.password_hash, role=EXCLUDED.role
            """, (username, nome, email, ph, role))
        conn.commit(); conn.close()
        print(f"Usuario '{username}' criado/atualizado.")
    elif cmd == "setpw":
        if len(sys.argv) < 3: print("uso: setpw <username>"); return
        username = sys.argv[2]
        pw = getpass.getpass("Nova senha: ")
        pw2 = getpass.getpass("Confirme: ")
        if pw != pw2: print("Senhas nao batem."); return
        ph = _hash_pw(pw)
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute("UPDATE reports.users SET password_hash=%s WHERE username=%s", (ph, username))
            if cur.rowcount == 0: print("Usuario nao encontrado."); return
        conn.commit(); conn.close()
        print(f"Senha de '{username}' atualizada.")
    elif cmd == "disable":
        if len(sys.argv) < 3: print("uso: disable <username>"); return
        username = sys.argv[2]
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute("UPDATE reports.users SET is_active=FALSE WHERE username=%s", (username,))
            if cur.rowcount == 0: print("Usuario nao encontrado."); return
        conn.commit(); conn.close()
        print(f"Usuario '{username}' desativado.")
    else:
        print(f"Comando desconhecido: {cmd}"); print(__doc__)


if __name__ == "__main__":
    _cli()
