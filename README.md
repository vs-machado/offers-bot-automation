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

## Coolify com PostgreSQL separado

Use apenas `docker-compose.coolify.yml` como Docker Compose Location no Coolify.
Esse arquivo não cria PostgreSQL nem publica portas diretamente no host.
`docker-compose.yml` e seu override continuam destinados ao ambiente local.

1. Crie e inicie um recurso PostgreSQL no mesmo servidor. Configure usuário,
   senha, banco e backups no recurso do banco.
2. Identifique a rede Docker à qual o PostgreSQL está conectado e defina
   `DATABASE_NETWORK` com esse nome. A rede deve existir antes do deploy.
   Os serviços da aplicação ingressam nela e mantêm uma rede interna própria
   para Redis e comunicação entre frontend e backend.
3. Copie o host interno, usuário, senha e banco da conexão fornecida pelo Coolify:

```dotenv
DATABASE_NETWORK=nome_da_rede_do_postgres
DATABASE_URL=postgresql+asyncpg://usuario:senha@host-interno:5432/offers_db
AUTH_DATABASE_URL=postgresql://usuario:senha@host-interno:5432/offers_db
BETTER_AUTH_URL=https://app.seudominio.com.br
BETTER_AUTH_SECRET=segredo_aleatorio_de_pelo_menos_32_caracteres
```

As duas URLs precisam apontar para o mesmo banco. Codifique caracteres especiais
do usuário e da senha para uso em URL. Não use `localhost` como host do banco.
`POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_DB` não configuram o recurso
separado; suas credenciais são administradas pelo Coolify.

4. Associe o domínio HTTPS ao frontend, porta interna 3000. Se usar QR para a
   conta operadora do Telegram, disponibilize acesso restrito ao worker na porta
   8081 durante essa configuração. Backend e posting não precisam de domínio.
5. Faça deploy e confira os logs do backend: as migrações executam antes de ele
   ficar saudável, e os demais serviços aguardam essa inicialização.

SMTP é opcional para cadastro e login; necessário para recuperar senha.
Se o banco anterior contém dados, importe um backup antes de trocar as conexões.
Trocar as URLs não transfere dados entre bancos.

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

Save only your Amazon Associates tag (for example, `yourtag-20`) in setup or settings. Product links use expanded Amazon URLs with your tag, not SiteStripe short links. Cookies, marketplace ID, and SiteStripe access are not required. Validation checks only the tag format; it does not authenticate with Amazon or confirm account ownership, eligibility, or commissions.

Amazon affiliate link generation through an API is planned but not yet implemented. The current flow expands short links, removes previous affiliate tracking, and adds the user's tag to the destination URL.

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

### Autenticação com Better Auth

Cadastro, acesso por senha, Google e sessões são gerenciados pelo Better Auth no
Next.js (`/api/auth/*`). As rotas antigas `/auth/register`, `/auth/login` e
`/auth/session/exchange` do FastAPI foram removidas. O proxy valida o cookie com
Better Auth e encaminha a sessão opaca ao FastAPI, que consulta sua validade no
PostgreSQL a cada requisição. Papéis de administrador continuam em `users.role`,
sem depender de variáveis enviadas pelo navegador.

A migração `0008_better_auth` cria as tabelas de autenticação e associa contas
existentes sem alterar seus IDs, configurações ou permissões. Senhas bcrypt
existentes continuam funcionando; novas senhas usam o hash padrão do Better Auth.
Sessões do NextAuth deixam de funcionar, exigindo novo login. A migração é
administrada pelo Alembic; não execute o CLI de migração do Better Auth sobre
essas mesmas tabelas. E-mails legados que colidam após conversão para minúsculas
precisam ser corrigidos antes da migração.

Configure `BETTER_AUTH_SECRET` (pelo menos 32 caracteres aleatórios),
`BETTER_AUTH_URL` (URL pública confiável) e `AUTH_DATABASE_URL` (PostgreSQL).
No Docker, a URL interna do banco é configurada pelo Compose. Para executar
Next.js localmente, coloque essas variáveis em `frontend/.env.local`.
Cadastre no Google o callback `${BETTER_AUTH_URL}/api/auth/callback/google`.
O vínculo automático de contas com o mesmo e-mail está desabilitado.

### Recuperação de senha

O link **Esqueci minha senha** abre `/forgot-password`. Better Auth gera um token
temporário, com identificador armazenado como hash e validade de 15 minutos.
O e-mail aponta para `/reset-password`, com token no fragmento da URL para evitar
que ele seja enviado em logs de acesso. O usuário confirma a senha duas vezes;
após a troca, todas as sessões antigas são revogadas e é necessário entrar de novo.
A resposta ao pedido é a mesma para e-mails conhecidos e desconhecidos.

Configure no servidor Next.js: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
`SMTP_PASSWORD` e `SMTP_FROM`. Para SSL direto, use `SMTP_SECURE=true` (geralmente
porta 465); para STARTTLS, `SMTP_SECURE=false` e `SMTP_REQUIRE_TLS=true` (geralmente
porta 587). Sem SMTP configurado, a tela informa que a recuperação está indisponível.
O servidor também envia um aviso após a alteração da senha. Dados de SMTP e links
de recuperação não são registrados nos logs da aplicação.

Os limites de tentativas ficam no PostgreSQL e são compartilhados entre instâncias
do frontend. Solicitações de recuperação permitem até três tentativas por minuto
por IP; login, cadastro e redefinição permitem cinco. O banco de autenticação
precisa estar disponível antes de iniciar o frontend. Execute a migração pelo
backend; em Docker, o frontend aguarda o healthcheck do backend.

### Configurações após o tutorial

A rota autenticada `/settings` permanece disponível pelos menus Configurações,
Grupos e Afiliados, no desktop e no celular. Permite cadastrar, editar, desativar
e remover destinos, selecionar grupos do catálogo da administração e atualizar
ou remover as integrações com Amazon, Mercado Livre, Shopee e AliExpress.
Cada alteração usa as APIs protegidas do próprio usuário. Habilitar um destino
verifica as permissões do bot. As credenciais cadastradas ficam mascaradas no
formulário; salvar não equivale a validar a autenticação na loja.

### Validação das credenciais de afiliado

O botão **Validar credenciais** está disponível nas quatro lojas, no tutorial
e em `/settings`. Consulta a rota autenticada
`POST /users/me/affiliate-credentials/validate` com os dados preenchidos no
formulário, mesmo antes de salvá-los. A verificação gera um link de referência
na loja, sem publicar no Telegram e sem persistir credenciais ou links de teste.

Resultados: aprovada, credenciais recusadas ou inconclusiva. Timeout, captcha,
limite de requisições e falhas da API não são confundidos com credenciais inválidas.
O Mercado Livre exige o link completo de um produto elegível, com ID MLB;
o endereço é enviado apenas à API fixa de afiliados e não é visitado pelo backend.
As demais lojas usam suas páginas iniciais como referência.

Modificar os dados oculta o resultado anterior. A validação comprova a geração
de um link naquele momento; não comprova titularidade da tag, comissão futura
ou elegibilidade de todas as ofertas. Salvar continua sendo uma ação separada.
As respostas contêm somente resultado, motivo e horário; nunca os segredos ou
a resposta bruta da loja. Requisições externas têm timeout de 20 segundos no
total, limite de oito validações simultâneas por processo e uma por usuário.

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

### WhatsApp destinations (WAHA)

Users can connect their own WhatsApp account in **Settings → Publicar no WhatsApp**,
scan the QR from **WhatsApp → Linked devices**, and select a group or channel from their account.
The same QR and destination picker is available in the setup tutorial. Telegram
group/channel configuration remains available alongside WhatsApp in both screens.
Each user receives a separate WAHA session (`offers-user-<application-user-id>`).
The API derives that name from the authenticated identity, never from browser input.
The connected account must participate in the group and have permission to send;
only WhatsApp channels with the `OWNER` or `ADMIN` role are selectable. If the WAHA
engine cannot list channels, the interface reports this while keeping groups available.
Messages are sent in that account's name, with the same prepared affiliate text/photo.

Operator setup:

1. Run WAHA with persistent session storage, API-key authentication, and support for
   multiple sessions and `sendImage`. The installed WAHA `2026.9.2` WEBJS build has
   these implementations; older builds may have different edition restrictions.
2. Make WAHA reachable from backend and posting containers. For the existing Coolify
   installation, attach its service to the external `coolify` Docker network with
   alias `waha`. Declare the network in WAHA's Compose file so recreation preserves it:

   ```yaml
   services:
     waha:
       networks:
         default:
         offers:
           aliases: [waha]
   networks:
     offers:
       external: true
       name: coolify
   ```

3. Set `WAHA_BASE_URL=http://waha:3000` and `WAHA_API_KEY=<operator WAHA API key>`
   in Offers Bot's Coolify environment, then deploy. Do not use `localhost`: from
   a container it points to that container, not WAHA. Backend startup applies
   migration `0009_whatsapp_destinations`, keeping existing destinations on Telegram.

WAHA credentials stay server-side; the browser receives only status, its own QR,
and group names/IDs. Pairing QR responses use `Cache-Control: no-store`. Unlinking
disables the user's WhatsApp destinations; queued jobs recheck enabled state and
ownership before delivery. WhatsApp sends use the existing Celery queue and expiry
rules. Text/photo sends with uncertain results are not automatically replayed.
The standalone legacy bot remains Telegram-only; WhatsApp is part of the multiuser
backend worker. Validate a real QR connection and test group after deployment.
