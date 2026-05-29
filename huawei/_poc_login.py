"""PoC #1: Login no FusionSolar e capturar tela inicial.
Validar que conseguimos passar do login sem captcha intratavel.

Usage:
    python _poc_login.py
"""
import os, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

LOGIN = "aevomaster"
SENHA = "Aevo@123"
URL_LOGIN = "https://la5.fusionsolar.huawei.com/unisso/login.action"
URL_TARGET = "https://la5.fusionsolar.huawei.com/uniportal/pvmswebsite/assets/build/cloud.html?app-id=smartpvms&instance-id=smartpvms&zone-id=a85e6744-6630-4ce9-bdc9-cb4892621115#/view/device/NE=53128738/inverter/history"

HERE = os.path.dirname(os.path.abspath(__file__))
SCREENSHOTS_DIR = os.path.join(HERE, "_screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Headless para rodar sem interferir. Se der captcha, mudar para False
    browser = p.chromium.launch(headless=True, slow_mo=100)
    ctx = browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
    )
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(f"PAGEERROR: {e}"))
    page.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)

    print(f"[1] Abrindo login: {URL_LOGIN}")
    page.goto(URL_LOGIN, wait_until="networkidle", timeout=30000)
    page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "01_login_page.png"))
    print(f"    URL atual: {page.url}")
    print(f"    Titulo: {page.title()}")

    # Tentar identificar os campos
    print("\n[2] Buscando campos de login...")
    selectors_login = [
        ('input[name="username"]', "name=username"),
        ('input#username', "id=username"),
        ('input[placeholder*="ome"]', "placeholder username pt"),
        ('input[type="text"]', "type=text"),
    ]
    user_input = None
    for sel, desc in selectors_login:
        el = page.query_selector(sel)
        if el:
            print(f"    [OK] Encontrado via {desc}: {sel}")
            user_input = sel; break
        else:
            print(f"    [--] Nao encontrado: {desc}")
    if not user_input:
        print("    ERRO: nao consegui localizar input de username")
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "02_no_username.png"))
        browser.close(); sys.exit(1)

    print(f"\n[3] Preenchendo {LOGIN} / ***")
    page.fill(user_input, LOGIN)
    pw_sel = 'input[type="password"]'
    page.fill(pw_sel, SENHA)
    page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "03_filled.png"))

    # Submit
    print("\n[4] Submetendo...")
    # Tentar botao por texto, depois enter
    btn_login = page.query_selector('button:has-text("Login"), button:has-text("Entrar"), button:has-text("Iniciar"), button[type="submit"]')
    if btn_login:
        btn_login.click()
    else:
        page.press(pw_sel, "Enter")

    # Aguarda redirect
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception as e:
        print(f"    Aviso aguardando networkidle: {e}")
    time.sleep(3)
    page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "04_after_login.png"))
    print(f"    URL pos-login: {page.url}")
    print(f"    Titulo: {page.title()}")

    # Detectar captcha
    if "captcha" in page.url.lower() or page.query_selector('img[src*="captcha"], canvas') is not None:
        print("\n[!] CAPTCHA DETECTADO — precisa intervencao manual")

    # Cookies relevantes
    cookies = ctx.cookies()
    print(f"\n[5] {len(cookies)} cookies apos login")
    for c in cookies[:5]:
        print(f"    {c['name']}: {c['value'][:30]}...")

    # Tentar abrir URL alvo
    print(f"\n[6] Navegando para URL alvo...")
    page.goto(URL_TARGET, wait_until="networkidle", timeout=30000)
    time.sleep(5)  # SPA, dar tempo de renderizar
    page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "05_target_inverter.png"))
    print(f"    URL atual: {page.url}")
    print(f"    Titulo: {page.title()}")

    # Salvar HTML para inspecao
    html = page.content()
    html_path = os.path.join(SCREENSHOTS_DIR, "target_page.html")
    with open(html_path, "w", encoding="utf-8") as f: f.write(html)
    print(f"\n[7] HTML salvo: {html_path} ({len(html):,} bytes)")
    print(f"    Tem 'inverter' no HTML: {'inverter' in html.lower()}")
    print(f"    Tem '<table' no HTML: {'<table' in html.lower()}")

    print(f"\nErros JS: {len(errors)}")
    for e in errors[:10]: print(f"  {e}")

    # Salvar storage state (cookies + localStorage) para reusar em proximas execucoes
    storage_path = os.path.join(HERE, "_storage_state.json")
    ctx.storage_state(path=storage_path)
    print(f"\n[8] Storage state salvo em {storage_path}")
    browser.close()

print("\nFim. Screenshots em:", SCREENSHOTS_DIR)
