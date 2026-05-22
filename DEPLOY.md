# Deploy — Painel AEVO19

Guia passo a passo para colocar o sistema online.

## Conceitos basicos (leitura rapida)

**Variavel de ambiente**: jeito de armazenar configuracoes (senhas, URLs) FORA do codigo. Em vez de escrever a senha no `app.py`, voce coloca em um lugar separado, e o codigo le de la. Vantagens: nao expoe a senha no Git, fica facil trocar sem reescrever codigo.

**.env**: arquivo local de texto com as variaveis. Ex:
```
SUPABASE_PASSWORD=minha-senha
```
**Nao se commita**: o `.gitignore` impede que seja enviado pro GitHub.

**Railway**: servico que hospeda o app online. As variaveis de ambiente sao definidas la no dashboard.

**Repositorio Git no GitHub**: o codigo precisa estar la para o Railway baixar e rodar.

---

## Fluxo

```
[seu codigo local] --git push--> [GitHub repositorio privado]
                                          |
                                          | Railway puxa
                                          v
                              [Railway monta + roda o app]
                                          ^
                                          |
                              [usuarios acessam via painelcep.aevosolar.com.br]
```

---

## Passo 1 — Criar conta GitHub (se ainda nao tem)

1. Vai em https://github.com
2. Cria conta com `matheush.albuquerque94@gmail.com`
3. Confirma email

## Passo 2 — Instalar GitHub CLI (`gh`)

Forma mais rapida de criar repo + push:

1. Baixa em https://cli.github.com (Windows installer)
2. Instala
3. Abre PowerShell e roda:
   ```
   gh auth login
   ```
4. Escolhe **GitHub.com** → **HTTPS** → **Login with browser**

## Passo 3 — Criar repo privado e dar push

Na pasta do projeto, no PowerShell ou Git Bash:

```bash
cd "C:\Users\mathe\OneDrive - AEVO Solar\PADRONIZAÇÃO\PLANEJAMENTO ENGENHARIA\TASKS\TASK - RELATÓRIOS\GERAÇÃO MENSAL\PYTHON"

# Cria repo privado no GitHub e ja faz push
gh repo create aevo-painel-cep --private --source=. --remote=origin --push
```

Resultado: repo criado em `https://github.com/<seu-user>/aevo-painel-cep`.

> **Alternativa sem `gh`**: criar repo manual no site do GitHub → copiar a URL `https://github.com/SEU-USER/aevo-painel-cep.git` → rodar:
> ```
> git remote add origin https://github.com/SEU-USER/aevo-painel-cep.git
> git push -u origin main
> ```

## Passo 4 — Criar projeto no Railway

1. Vai em https://railway.app (faz login se necessario, usa GitHub)
2. **New Project** → **Deploy from GitHub repo**
3. Autoriza Railway a acessar seus repos
4. Escolhe `aevo-painel-cep`
5. Railway detecta o `requirements.txt` + `Procfile` e comeca o build

**O primeiro build leva ~5min** (instala Playwright + Chromium). Acompanha em **Deployments → Build Logs**.

## Passo 5 — Configurar variaveis de ambiente

Ainda no Railway, no servico criado:

1. Aba **Variables**
2. Clica **+ New Variable** e adiciona uma a uma:

| Variavel | Valor (copia do seu .env local) |
|---|---|
| `SUPABASE_HOST` | `db.zaqeviptywgrnhrtmfmh.supabase.co` |
| `SUPABASE_PORT` | `5432` |
| `SUPABASE_DB` | `postgres` |
| `SUPABASE_USER` | `postgres` |
| `SUPABASE_PASSWORD` | (sua senha) |
| `SUPABASE_REGION` | `us-east-1` |
| `AEVO_HOST` | `shinkansen.proxy.rlwy.net` |
| `AEVO_PORT` | `18796` |
| `AEVO_DB` | `railway` |
| `AEVO_USER` | `powerbi_readonly_user` |
| `AEVO_PASSWORD` | `Rogin@Aevo123` |
| `TZ` | `America/Sao_Paulo` |

3. Apos salvar, Railway **redeploy automaticamente**.

## Passo 6 — Configurar dominio customizado

1. No Railway, aba **Settings** do servico → **Networking** → **Custom Domain**
2. Digite: `painelcep.aevosolar.com.br`
3. Railway mostra um valor CNAME tipo `aevo-painel-cep-xxxx.up.railway.app`
4. **No painel do seu DNS** (Registro.br, Cloudflare, etc):
   - Adiciona um **registro CNAME**:
     - Nome: `painelcep`
     - Tipo: `CNAME`
     - Valor: o valor que o Railway mostrou
     - TTL: 3600
5. Aguarda ~10min para propagar
6. Railway emite certificado SSL automaticamente

## Passo 7 — Acessar o painel

`https://painelcep.aevosolar.com.br`

Tela de login aparece. Usa:
- **usuario**: `matheus`
- **senha**: a temporaria que recebeu na criacao (`mzNBojdXo!2Wudko`)

Depois do primeiro login, **troca a senha** rodando localmente:
```
python auth.py setpw matheus
```

## Passo 8 — Criar usuarios para a equipe

```
python auth.py create alex alex@aevosolar.com.br "Alex Silva" user
python auth.py create maria maria@aevosolar.com.br "Maria Souza" user
python auth.py list
```

---

## Passo 9 — Servico do Cron (ETL diario)

O cron roda **separado** do app principal (mesmo repo, comando diferente).

1. No Railway, dentro do mesmo projeto, clica **+ New** → **Empty Service**
2. Conecta o mesmo repo
3. Em **Settings → Build & Deploy**:
   - **Root Directory**: `etl`
   - **Start Command**: `python cron_runner.py`
4. **Variables**: copia as MESMAS do app principal (Railway tem opcao "Share variables")
5. **Schedule** (aba **Cron**):
   - Activate cron schedule
   - Expression: `0 5 * * *` (todo dia 02:00 BRT = 05:00 UTC)
6. Salva — primeira execucao acontece no proximo horario configurado

Para testar antes: clica **Deploy** uma vez manualmente.

---

## Resumo de custos esperados

| Servico | Custo |
|---|---|
| Railway app web | ~$5/mes (Hobby) |
| Railway cron job | ~$1-2/mes (poucos minutos de uso) |
| Supabase | $0 (free tier) |
| Dominio aevosolar.com.br | ja existente |
| **Total** | **~$6-10/mes** |

---

## Resolver problemas comuns

**Build falhou no Railway**: verifica logs em **Deployments → Build Logs**. Erro comum: Playwright nao baixou o Chromium. Solucao: garantir que `railway.json` tem `playwright install --with-deps chromium` no install phase.

**App esta no ar mas da erro 500**: ver **Deploy Logs**. Geralmente: alguma variavel de ambiente nao foi definida.

**Login nao funciona**: confirma que a tabela `reports.users` no Supabase tem o usuario (use Table Editor no Supabase).

**Dominio nao resolve**: aguarda 1h. DNS pode demorar.

---

## Atualizar codigo depois

Quando voce mudar algo localmente:

```
git add .
git commit -m "descricao do que mudou"
git push
```

Railway detecta o push e **redeploy automaticamente** em ~2min.
