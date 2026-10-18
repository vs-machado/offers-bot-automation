# WAHA: recomendações para implementação de canais

## Objetivo

Conectar contas WhatsApp e publicar em **canais**, com integração na interface,
tutorial e configurações do bot. Origem das ofertas continua sendo o catálogo
Telegram; distribuição usa os destinos habilitados de cada usuário.

Este documento deve orientar implementação, revisão e validação da feature.
As medidas abaixo reduzem abuso e falhas operacionais, mas não garantem ausência
de banimento: WAHA é um cliente não oficial.

## Requisitos de implementação

### Frequência por conta e canal

- Espaçar e serializar publicações no mesmo canal, inclusive com workers concorrentes.
- Controlar também volume agregado por conta: múltiplos canais compartilham a sessão.
- Permitir configurar intervalo mínimo, teto por hora/dia e janela de publicação.
  Documentar valores escolhidos e sua justificativa editorial/operacional.
- Não apresentar valores como cotas "seguras": não há limite público comprovado
  contra banimento para canais via WAHA.
- Ao atingir limite, adiar apenas ofertas ainda válidas; não acumular backlog ilimitado.

### Deduplicação e validade

- Deduplicar mesma oferta recebida de origens diferentes por produto/link normalizado.
- Preservar variações de produto e parâmetros necessários aos links de afiliado.
- Aplicar deduplicação por destino e janela temporal, inclusive sob concorrência.
- Permitir republicação por mudança relevante, como preço, mediante regra explícita.
- Preservar validade desde entrada até envio e revalidar destino habilitado antes
  da entrega.
- **Limite máximo definido: 10 minutos (600 segundos).** Ofertas com idade igual
  ou superior a esse limite devem expirar sem publicação. Contar desde timestamp
  da mensagem de origem, usando entrada na fila somente quando origem não tiver
  timestamp. Reprocessamento, retry, reconexão e reinício não renovam esse prazo.
- Configuração pode definir validade menor, nunca superior a 600 segundos.
  Na implementação, alinhar `PROMOTION_TTL_SECONDS`, expiração no broker e
  verificação imediatamente anterior ao envio com esse limite.
- Após queda ou reinício, descartar ofertas vencidas e retomar com espaçamento,
  sem despejar backlog em rajada.

### Rajadas: priorizar as 5 ofertas mais recentes

- Quando muitas ofertas chegarem em intervalo curto, reduzir backlog por canal
  às **5 ofertas elegíveis mais recentes**, descartando pendentes mais antigas
  daquela rajada. Volume concentrado indica risco de ofertas já esgotadas; não
  equivale a confirmação de estoque indisponível.
- Tornar janela de detecção e quantidade mínima que caracteriza rajada
  configuráveis. Definir e documentar valores antes de implementar; quantidade
  mantida inicialmente é 5.
- Considerar chegada das ofertas elegíveis ao sistema para detectar concentração;
  ordenar por timestamp da origem, com fallback para entrada na fila, para escolher
  as mais recentes. Usar desempate determinístico.
- Aplicar deduplicação e validade antes da seleção: duplicatas e ofertas vencidas
  não devem ocupar as 5 posições. Não recuperar descartadas para preencher vagas.
- Seleção é por canal e entre origens, preservando isolamento de usuários. Aplicar
  também ao backlog acumulado na retomada após indisponibilidade.
- Selecionar 5 não autoriza publicá-las juntas: manter limites por conta/canal e
  espaçamento. Oferta selecionada que vencer enquanto aguarda deve expirar.
- Descartar somente entregas ainda pendentes; não cancelar envio já iniciado nem
  reenviar entrega concluída ou incerta. Coordenar seleção e início de envio para
  evitar corrida entre workers.
- Registrar motivo específico de descarte por rajada, distinto de expiração ou
  confirmação de falta de estoque. Jobs descartados não devem voltar via retry.

### Pausa automática e recuperação

- Distinguir restrição temporária, falha de autenticação, falta de permissão,
  destino inválido e falha de transporte quando upstream permitir.
- Pausar conta/canal diante de restrição ou falhas repetidas; mostrar motivo e
  estado nas configurações.
- Usar espera progressiva e respeitar `Retry-After` quando disponível.
- Não reiniciar, deslogar ou refazer pareamento em loop para remover restrições.
- Não repetir automaticamente envio com resultado incerto: timeout pode ocorrer
  depois de publicação aceita. Registrar estado incerto para investigação.
- Erros `463` e `475` descritos pelo WAHA tratam de contatos novos; não assumir
  que sejam cotas de canal nem que correspondam a status HTTP idênticos.

### Conta, sessão e interface

- Isolar sessão por usuário autenticado; não aceitar sessão arbitrária do navegador.
- Manter API key de operador somente no servidor e QR acessível somente ao dono.
- Listar e aceitar apenas canais em que conta tenha papel `OWNER` ou `ADMIN`.
- Persistir sessões e evitar pareamentos desnecessários.
- Validar compatibilidade de versão/engine com canais, texto e imagem nas atualizações.
- Permitir pausar cada destino e desconectar conta nas configurações.
- Desconexão desativa destinos WhatsApp; retomada exige reconexão e habilitação explícita.
- Exibir estados de conexão, falha, pausa e recuperação no tutorial/configurações.
- Não deixar falha na listagem de grupos bloquear canais.
- Registrar tentativas, destino, resultado e motivo de falha/expiração sem API key ou QR.

### Conteúdo e particularidades de canais

- Priorizar ofertas relevantes, links confiáveis e indicação de links de afiliado.
- Evitar conteúdo enganoso, repetitivo, expirado ou volume incompatível com proposta do canal.
- Não enviar mensagens privadas ou convites em massa aos seguidores neste fluxo.
- Uma publicação em canal não equivale a uma chamada de envio por seguidor.
- Não aplicar automaticamente recomendações de conversas privadas, como marcar
  leitura e simular digitação, a canais.
- Não tratar delays aleatórios, "aquecimento", proxies ou alterações artificiais
  de texto como garantia de proteção contra banimento.

## Critérios de validação

- Isolamento entre usuários e seleção apenas de canais administrados.
- Envio real de texto e imagem em canal de teste.
- Limites preservados com jobs concorrentes e múltiplos canais na mesma conta.
- Deduplicação entre origens e reprocessamentos.
- Rajada mantém somente as 5 ofertas elegíveis mais recentes por canal; verificar
  ordenação, múltiplas origens, isolamento, concorrência e retomada após queda.
- Ofertas descartadas por rajada não reaparecem em retries; selecionadas continuam
  respeitando espaçamento e prazo máximo de 600 segundos.
- Descarte de oferta vencida e retomada sem rajada após indisponibilidade.
- Descarte no limite de 600 segundos, incluindo ofertas que já chegaram antigas
  à fila e retries/reconexões que não podem renovar a validade.
- Pausa por restrição/falhas e cancelamento ao desabilitar destino.
- Ausência de reenvio automático quando resultado de entrega for incerto.
- Tutorial e configurações coerentes com conexão, destinos e pausas.

## Estado observado e próximos passos

Destinos Telegram e WhatsApp têm seleção independente de categorias na interface
de setup e configurações. `categories = NULL` recebe tudo; lista vazia não recebe
ofertas. As regras são verificadas antes da entrada na fila e novamente antes da
entrega, inclusive após adiamento por limites. Migração necessária:
`0013_destination_categories`. Categorias bloqueadas não ocupam vagas em novas
rajadas quando a regra já está salva.

Base existente: sessões por usuário, QR, canais administrados, destinos e envio
pela fila Celery, com expiração e tratamento conservador de reenvio. Interface
e tutorial receberam complementos nesta branch.

Implementados nesta branch: validade máxima de 600 segundos, limites por conta e
destino, deduplicação transacional entre origens por produto/variação e preço
(janela de 30 minutos), retenção das 5 mais recentes em rajadas e backlog,
pausa automática e controles na interface/tutorial. Alteração de preço permite
nova publicação; destinos e usuários têm deduplicação independente.

Valores iniciais, definidos como política editorial e não como garantia antiban:

| Controle | Padrão |
| --- | --- |
| Validade | 600 segundos, limitada também por `PROMOTION_TTL_SECONDS` do operador |
| Intervalo agregado por conta | 30 segundos |
| Intervalo por destino | 60 segundos |
| Tentativas por conta | 60/hora e 300/24h, em janelas móveis |
| Rajada | 6 ofertas elegíveis em 60 segundos; manter 5 pendentes mais recentes |
| Coleta inicial por oferta de canal | 60 segundos (acompanha janela configurada de rajada) |
| Janela de publicação | 0–24h UTC (dia inteiro), configurável sem atravessar meia-noite |
| Falhas consecutivas | 3 falhas: pausa de conta por 15 minutos |
| Autenticação/permissão/destino recusados | Pausa imediata por 15 minutos |
| Limitação explícita HTTP 429 | Pausa por pelo menos 60 segundos ou `Retry-After`, se maior |

Permissões/destino pausam somente o destino; autenticação, limitação e falhas
repetidas pausam a conta. Respostas e status internos de erro não são presumidos
iguais a códigos HTTP. Retomada manual remove pausas, sem habilitar destinos ou
recuperar ofertas descartadas. Expiração é antecipada quando não há margem para
iniciar uma requisição antes do prazo.

Workers usam lock transacional por usuário no PostgreSQL para coordenar
deduplicação, corte de rajada e reserva de envio entre processos. Reserva ativa
impede envios WhatsApp concorrentes na mesma conta; cada tentativa conta para
os limites, inclusive quando falha. Nenhuma credencial é interpolada em SQL.

Deploy requer migration `0010_whatsapp_delivery_policy` antes de iniciar os
workers atualizados. **Ainda pendente:** teste ponta a ponta com QR e envio real
de texto/imagem num canal, após deploy. Testes automatizados usam PostgreSQL
descartável e não enviam mensagens reais.

## Testes automatizados

Validação direcionada:

```bash
python -m unittest tests.test_whatsapp_delivery_policy tests.test_whatsapp tests.test_backend_worker
```

Para incluir testes de concorrência, definir `WAHA_POLICY_TEST_DATABASE_URL` para
banco PostgreSQL de teste descartável, nunca produção. Cada teste cria e remove
seu próprio schema. CI de PR fornece esse banco automaticamente.

## Referências

Consultadas em 15/10/2026:

- [WAHA — How to Avoid Blocking](https://waha.devlike.pro/docs/overview/how-to-avoid-blocking/)
- [WAHA — Channels](https://waha.devlike.pro/docs/how-to/channels/)

Guia de bloqueios contém recomendações majoritariamente para mensagens privadas
e relatos heurísticos. Não tratar intervalos, quantidade de denúncias ou supostos
"pontos de reputação" como regras oficiais ou evidência de segurança para canais.
