# Telegram Offers Bot

Multi-tenant offers automation. Shared worker listens to the platform Telegram source catalog through Telethon, extracts supported product links, generates each user's affiliate links, and posts through platform bot to that user's enabled destinations.

## Runtime architecture

```mermaid
flowchart LR
    UI[Dashboard setup] --> DB[(PostgreSQL)]
    DB --> W[Shared worker]
    S[Public Telegram sources] --> W
    W --> P[Offer parser]
    P --> A[User affiliate client]
    A --> B[Platform Telegram bot]
    B --> D[User destinations]
```

- Dashboard saves `source_chats`, destinations, and Amazon/Shopee/Mercado Livre/AliExpress credentials in PostgreSQL.
- Worker reloads persisted config every 30 seconds.
- One operator-owned Telethon account receives catalog messages and fans them out to subscribed users. Users select catalog groups and cannot add their own sources.
- Real Telegram post IDs plus PostgreSQL records provide per-user deduplication.
- Destination posting uses one platform bot. Users do not create their own bots or Telegram sessions.

## Parsing

Qwen 3.7 Flash (`qwen/qwen3.7-flash`) through OpenRouter is the primary structured parser. DeepSeek V4 Flash and Gemini 2.5 Flash Lite use direct provider APIs as fallbacks. Regex parser runs when AI credentials are absent or AI parsing fails.

URL routing and affiliate conversion support:

- Mercado Livre
- Amazon Brazil
- Shopee Brazil
- AliExpress

## Setup

1. Create platform bot with `@BotFather` and copy token.
2. Copy `.env.example` to `.env` and set platform infrastructure/auth secrets. User settings and affiliate credentials do not belong in `.env`.
3. Start stack:

```powershell
docker compose up --build
```

4. Register/login in frontend.
5. Complete dashboard setup:

   - add platform bot to destination group/channel;
   - grant bot permission to post messages and photos;
   - save destination chat ID;
   - save credentials for one or more affiliate providers;
   - select Telegram source groups from the platform catalog.

Worker begins processing after next 30-second refresh.

## Database migrations

Backend runs `alembic upgrade head` during startup.

Run migrations manually from repository root with project virtual environment:

```powershell
.\venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head
```

## Configuration boundaries

User-owned business configuration is stored only in PostgreSQL through authenticated `/users/me` endpoints:

- destination chat IDs and enabled state;
- selected source chats;
- affiliate tags, API keys, cookies, CSRF tokens, and tracking IDs;
- optional browser resolver settings if later exposed by dashboard/API.

`.env` contains platform infrastructure only:

- shared `TELEGRAM_BOT_TOKEN`;
- database/auth/OAuth secrets;
- optional shared AI parser credentials.

The operator reader uses `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and its shared session/QR settings. `SOURCE_CHATS`, `TARGET_CHAT`, and affiliate environment variables are legacy CLI settings; the shared worker takes catalog subscriptions, destinations, and affiliate settings from PostgreSQL.

## Provider credentials

### Mercado Livre

Save affiliate tag, authenticated cookie header, and CSRF token in dashboard. Cookies expire; update provider config when API begins returning 401/403.

### Amazon

Save Associates tag, authenticated cookie header, and optional marketplace ID. Default marketplace ID is `526970`.

### Shopee

Save Affiliate Open Platform app ID and app secret.

### AliExpress

Save Affiliate API app key, app secret, and optional tracking ID.

## Local quality checks

### Pre-commit automático

Instale as ferramentas de desenvolvimento e ative o hook uma vez por clone:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm --prefix frontend ci
.\venv\Scripts\python.exe -m pre_commit install --install-hooks
```

Antes de cada commit, Ruff corrige e formata o Python; ESLint verifica todo o frontend com correções automáticas e `--max-warnings 0`. Todos os hooks rodam mesmo se o commit não alterar arquivos Python ou JavaScript. Se houver correções, o commit é interrompido: revise o diff, adicione os arquivos corrigidos e tente novamente. Erros e warnings restantes bloqueiam o commit. O hook não adiciona arquivos ao índice automaticamente.

ESLint também verifica classes canônicas do Tailwind 4 usando
`better-tailwindcss/enforce-canonical-classes`, com o tema de `app/globals.css`.
Sugestões como `md:w-[440px]` → `md:w-110` passam a ser erros corrigíveis pelo
mesmo hook. O diagnóstico do Tailwind IntelliSense permanece habilitado no editor.

Para executar a mesma verificação manualmente:

```powershell
.\venv\Scripts\python.exe -m pre_commit run --all-files
npm --prefix frontend run lint:fix
```

Ruff remove `noqa` desnecessário com `RUF100` e o hook usa `--ignore-noqa`, para que essas anotações não escondam erros. ESLint não aceita comentários para desativar regras. Corrija a causa do diagnóstico; não esconda o problema com supressões ou desativando regras. Os testes continuam sendo executados antes de cada commit, conforme `AGENTS.md`.

Use project virtual environment:

```powershell
.\venv\Scripts\ruff.exe format .
.\venv\Scripts\ruff.exe check --fix .
.\venv\Scripts\python.exe -m unittest discover tests
```

## Troubleshooting

- Destination save fails: confirm platform bot is administrator and can post messages/photos.
- User stays inactive: confirm enabled destination, at least one complete affiliate provider, and saved source selection all exist.
- Source returns no messages: check the operator Telethon account can access every catalog group.
- New config is not active: allow one 30-second worker cycle.
- AI keys missing: regex parsing continues automatically.

### Shared Telegram reader

Set `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` for the operator account. Supply `TELEGRAM_SESSION_STRING` or set `TELEGRAM_PHONE` and scan the QR served on port 8081. Operator sessions, LLM accounting, catalog sources, user destinations and affiliate credentials are persisted in PostgreSQL. Docker mounts `data` for temporary media and legacy import files. Set `OPENROUTER_API_KEY` to enable the primary Qwen parser.

### Migração da persistência da plataforma

Configure `DATABASE_URL` conforme `.env.example`. A porta local padrão é 5434;
dentro do Docker, os serviços usam `db:5432`. Instale as dependências atualizadas.
O backend aplica a migração `0005_platform_persistence` ao iniciar.

Para importar sessão do operador e histórico de tokens de uma instalação anterior,
pare o worker e execute, com o banco e o backend disponíveis:

```powershell
docker compose up -d db backend
.\venv\Scripts\python.exe -m backend.import_sqlite data/offers.sqlite3
docker compose up -d worker
```

A importação é transacional e pode ser repetida usando o mesmo arquivo. Não altera
o SQLite nem sobrescreve sessões já existentes no PostgreSQL. Os IDs de origem
identificam um único banco legado; não use esse comando para combinar arquivos
SQLite independentes. Ofertas do bot antigo não são importadas: sua deduplicação
global não identifica o usuário exigido pelo modelo da plataforma.

O bot legado executado separadamente continua compatível com SQLite. A plataforma
usa PostgreSQL; `DATABASE_PATH` serve apenas ao modo legado e à importação.

### Configurações após o tutorial

A rota autenticada `/settings` permanece disponível pelos menus Configurações,
Grupos e Afiliados, no desktop e no celular. Permite cadastrar, editar, desativar
e remover destinos, selecionar grupos do catálogo da administração e atualizar
ou remover as integrações com Amazon, Mercado Livre, Shopee e AliExpress.
Cada alteração usa as APIs protegidas do próprio usuário. Habilitar um destino
verifica as permissões do bot. As credenciais cadastradas ficam mascaradas no
formulário; salvar não equivale a validar a autenticação na loja.

### Histórico de publicações

O dashboard consulta `GET /users/me/deliveries`, autenticado e limitado aos
registros do próprio usuário. Inclui paginação, filtro por resultado e atualização
a cada 30 segundos. Os totais exibidos vêm do banco; não são dados demonstrativos.
O histórico aparece também enquanto a configuração está incompleta.

A migração `0007_delivery_details` adiciona título, loja e etapa aos novos
registros. Motivos são classificados e apresentados em português: autenticação,
chave de API, permissões do bot, limites de envio, conectividade, falha da API,
fila indisponível e prazo vencido. Respostas brutas, cookies, tokens e chaves
não são enviados ao navegador. Quando a resposta não identifica a causa,
o histórico mostra uma falha genérica, sem presumir que a chave está inválida.

Falhas na conversão de links são registradas antes da fila, por destino.
Uma falha do LLM recuperada por fallback não é tratada como postagem fracassada.
Uma desconexão do leitor impede receber novas promoções e, portanto, não produz
registros por promoção; seu diagnóstico depende dos logs operacionais.

### Fila de postagem de promoções

O listener prepara os links e publica uma tarefa por destino no Redis. O serviço
`posting` executa essas tarefas com Celery. O prazo padrão é de 180 segundos desde
a data original da mensagem do Telegram, incluindo processamento; ajuste
`PROMOTION_TTL_SECONDS` no ambiente do listener. Promoções vencidas são descartadas.
Não há Celery Beat: o envio é acionado por mensagens, sem agendamento periódico.

```powershell
docker compose up -d --build db redis backend worker posting
```

O Redis não grava snapshots nem AOF. Reiniciar o Redis perde tarefas pendentes;
elas não são reconstruídas a partir do banco. A memória é limitada a 256 MB, com
`noeviction`: atingir o limite faz a publicação falhar, sem expulsar silenciosamente
mensagens. `POSTING_CONCURRENCY` controla os processos de envio (padrão: 2).

`promotion_deliveries` registra estado por usuário e destino. Antes do envio,
o consumidor confirma que o destino continua cadastrado e habilitado. Uma tarefa
duplicada não repete um envio já iniciado. Existem até duas novas tentativas para
falhas de conexão anteriores ao envio e respostas 429, respeitando `retry_after`
e o prazo restante. Falhas ambíguas são marcadas como `uncertain`, sem repetição
automática. Telegram não fornece uma chave de idempotência para esse envio;
o sistema prioriza evitar duplicação, podendo perder uma postagem após uma queda.

Imagens locais são copiadas para a mensagem da fila antes da limpeza pelo listener,
com limite de 8 MB; imagens maiores são omitidas. URLs de imagens são enviadas ao
Telegram. Uma rejeição explícita da foto (400) permite tentar apenas o texto.

O histórico não contém o conteúdo das promoções nem funciona como uma fila
persistente. Após perda do Redis, registros `queued` ou `retrying` podem permanecer
no banco; quando `expires_at` passa, devem ser interpretados como expirados.
`sending` sem conclusão indica resultado incerto. Não reenvie esses registros
automaticamente.

Execução local exige Redis acessível em `REDIS_URL`. Em Windows, use Docker para
o consumidor Celery; para desenvolvimento sem Docker, o modo `--pool=solo` evita
o pool de processos, mas Celery não oferece suporte oficial a Windows.

### Administrator access and source catalog

The `/admin/source-groups` screen and every `/admin/source-groups` API operation require the `admin` role. The API checks the current database role on every request; changing or revoking a role applies even to existing tokens. Public registration always creates a `user` account.

Apply migration `0004_admin_source_catalog` (automatically on backend startup). It gives existing users the `user` role and seeds the seven original Telegram sources once. Register your administrator account, then promote it through trusted operator access:

```powershell
.\venv\Scripts\python.exe -m backend.set_admin admin@example.com
# Revoke administrator access:
.\venv\Scripts\python.exe -m backend.set_admin admin@example.com --role user
```

With Docker, run `docker compose exec backend python -m backend.set_admin admin@example.com` after the account is registered. No public API grants administrator roles.

Administrators can add, edit, enable, disable, and remove public Telegram groups. Only enabled groups are selectable by users and accepted by configuration endpoints. The shared Telethon reader refreshes catalog changes every 30 seconds without restarting; removed or disabled groups stop delivering offers. Saved selections for unavailable groups stay stored but inactive until the group becomes available again. An empty catalog disables all sources. The operator Telegram account must be able to join/read each source.
