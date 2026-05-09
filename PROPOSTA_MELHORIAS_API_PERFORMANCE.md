# Proposta de Melhorias: Performance e Melhor Uso da API OathNet

## Objetivo

Este documento resume melhorias tecnicas para o projeto `nexus_osint`, com foco em:

- reduzir latencia media das buscas
- diminuir consumo desnecessario de quota da OathNet
- aproveitar melhor os recursos ja expostos pela API documentada em `apiOathnet.yamal.txt`
- reduzir custo de memoria e payload no fluxo SSE

## Resumo Executivo

O principal problema atual nao esta no `httpx.AsyncClient`, que ja reutiliza conexoes corretamente, mas sim no desenho do fluxo de busca:

1. a aplicacao usa a OathNet sem inicializar e propagar `search_id` no fluxo principal SSE
2. o orquestrador existe, mas quase nao executa trabalho real em paralelo
3. a integracao consome respostas maiores do que o necessario e ignora filtros/parametros importantes da API v2
4. o cache atual e muito simples para o tipo de busca que a aplicacao faz

Resultado pratico:

- mais chamadas do que o necessario
- menor rastreabilidade de quota por sessao
- latencia acumulada por chamadas seriais
- payloads SSE grandes, com mais memoria e serializacao do que o necessario

## Evidencias no codigo

### 1. `search_id` recomendado pela spec nao e usado no fluxo principal

A spec da OathNet recomenda criar uma sessao em `/service/search/init` e reutilizar `search_id` nas chamadas subsequentes.

Hoje isso existe no client:

- `modules/oathnet_client.py:229` implementa `init_session()`
- `modules/oathnet_client.py:243`, `301`, `336`, `353`, `360`, `367`, `378`, `385`, `392`, `399`, `447`, `482`, `534` aceitam `search_id`

Mas o fluxo principal SSE nao usa isso:

- `api/services/search_service.py:249` chama `search_breach(query)` sem `session_id`
- `api/services/search_service.py:258` chama `search_stealer_v2(query)` sem `session_id`
- `api/services/search_service.py:300` chama `holehe(query)` sem `session_id`
- `api/services/search_service.py:349+` faz o mesmo com outros endpoints auxiliares

Tambem ha perda de contexto nas rotas auxiliares:

- `api/routes/search.py:63` pagina breach via cursor sem `search_id`
- `api/routes/victims.py:31` usa `victims_search(..., "", **filters)` e descarta sessao

Impacto:

- quota e analytics deixam de ficar agrupados por busca
- a aplicacao nao segue o fluxo recomendado pela API
- paginação e buscas relacionadas perdem contexto de sessao

### 2. O orquestrador existe, mas o trabalho real continua majoritariamente serial

O projeto possui um `TaskOrchestrator` robusto:

- `api/orchestrator.py` define limite global e limite especifico para OathNet

Mas no fluxo real ele quase nao e usado para executar modulos:

- `api/services/search_service.py:159-164` registra apenas um "sentinel"
- o restante da funcao `_stream_search()` roda em blocos sequenciais

Na pratica:

- breach + stealer usam `asyncio.gather()` localmente
- holehe roda depois
- discord auto roda em loop serial
- steam, xbox, roblox, victims, ghunt, ip_info e subdomain rodam um apos o outro

Impacto:

- o tempo total da busca vira a soma de varios modulos
- a degradacao por memoria nao controla de fato o mix real de tarefas externas
- a arquitetura implementada e melhor do que o fluxo que a utiliza

### 3. A integracao nao usa recursos importantes da API v2

A spec exposta em `apiOathnet.yamal.txt` mostra suporte a:

- `fields[]` para whitelisting de campos
- `filter` e `filter_id` para filtros estruturados
- `page_size`
- `dbnames`
- endpoints v2 especificos para victims, stealer, exports e bulk search

Hoje o client usa apenas uma parte pequena disso:

- `modules/oathnet_client.py:238-328` cobre breach e stealer basicos
- `modules/oathnet_client.py:467-502` cobre victims search

O que falta na pratica:

- `search_breach()` nao aceita `dbnames`, `fields[]` nem filtros estruturados
- `search_stealer_v2()` nao aceita `fields[]`, `filter`, `filter_id`, `sort`, `from`, `to`, `date_field`, `logic`
- nao existe wrapper para bulk search/export, apesar da spec documentar esses fluxos

Impacto:

- overfetch: mais dados trafegados e parseados do que o frontend precisa
- menor precisao de busca
- perda de oportunidade para tarefas pesadas virarem jobs async na OathNet

### 4. O cache atual e util, mas simplificado demais

O cache atual:

- `api/services/search_service.py:20` usa `TTLCache(maxsize=200, ttl=300)`
- `api/services/search_service.py:26` gera chave por `endpoint + query`

Problemas:

- parametros como `cursor`, `page_size`, filtros, `fields[]` e `search_id` nao entram na chave
- o cache nao esta preparado para crescer com busca v2 mais rica
- o objeto armazenado inclui estruturas completas, inclusive `raw_response` e `raw` dos records

Impacto:

- alto risco de cache inadequado quando a integracao ficar mais sofisticada
- uso de memoria maior que o necessario
- reuso de cache limitado a poucos cenarios

### 5. O payload SSE esta maior do que precisa

Hoje o backend envia:

- ate `MAX_BREACH_SERIALIZE = 200` breaches por evento
- listas completas de breaches e stealers no SSE inicial

Evidencia:

- `api/config.py:70` define `MAX_BREACH_SERIALIZE = 200`
- `api/services/search_service.py:308-334` envia o pacote completo no evento `oathnet`

Impacto:

- aumento de serializacao JSON
- mais memoria temporaria por request
- maior custo de render no frontend
- atraso no primeiro paint de resultados

## Melhorias recomendadas

## Prioridade 1: Corrigir o modelo de sessao com `search_id`

### Proposta

- iniciar a busca SSE com `init_session(query)` uma unica vez
- propagar o `session_id` para todos os wrappers OathNet daquele request
- devolver `session_id` ao frontend para paginação subsequente
- alterar `/api/search/more-breaches` e `/api/victims/search` para aceitarem `search_id`

### Beneficios

- melhor controle de quota por busca
- aderencia ao fluxo recomendado pela OathNet
- contexto consistente entre primeira busca, paginação e enriquecimentos

### Complexidade

Baixa a media.

## Prioridade 2: Usar o `TaskOrchestrator` de verdade

### Proposta

Trocar o fluxo serial de `_stream_search()` por submissao real de tarefas:

- `breach`, `stealer`, `holehe`, `victims`, `ip_info`, `steam`, `xbox`, `roblox`, `ghunt`, `subdomain`
- marcar como `is_oathnet=True` os modulos que usam a OathNet
- consumir resultados conforme forem chegando, emitindo SSE incremental

### Beneficios

- menor latencia total
- controle centralizado de concorrencia
- degradacao de memoria passa a ter efeito real nas chamadas externas

### Observacao importante

Faz sentido manter algumas dependencias seriais quando houver relacao funcional, por exemplo:

- auto Discord a partir de `discord_id` encontrado em breach

Mas o resto nao deveria bloquear essa etapa.

## Prioridade 3: Reduzir overfetch usando `fields[]` e filtros

### Proposta

Adicionar suporte no client para:

- `fields[]` em breach e stealer
- `dbnames` quando a UI quiser restringir fontes
- `filter` e `filter_id` nas rotas v2
- `page_size` configuravel por modulo

### Estrategia pratica

Para a tela principal, buscar um conjunto minimo de campos:

- breach: `email`, `username`, `ip`, `domain`, `date`, `dbname`, `discord_id`, `phone`
- stealer: `url`, `domain`, `username`, `email`, `log_id`, `pwned_at`

Deixar campos pesados ou raros para fetch sob demanda.

### Beneficios

- menos banda
- menos parse
- menos memoria por resposta
- frontend mais rapido

## Prioridade 4: Criar wrappers para bulk search e exports

### Proposta

A spec mostra suporte a jobs async. Isso deve ser usado para buscas grandes ou operacoes administrativas.

Implementar no client:

- criar bulk search job
- consultar status
- baixar resultado
- criar export de victims/breach quando aplicavel

### Quando usar

- listas grandes de emails
- dominios com muitas ocorrencias
- relatorios offline
- casos em que SSE online deixaria a request longa demais

### Beneficios

- remove carga do request-response interativo
- melhor aproveitamento da API OathNet
- reduz timeouts e retries no backend

## Prioridade 5: Melhorar o cache

### Proposta

Substituir a chave atual por uma chave parametrica canonica, por exemplo:

`(endpoint, query, cursor, page_size, sorted_filters, sorted_fields, dbnames)`

Tambem recomendo:

- nao cachear objetos com `raw_response` completo quando o frontend nao precisa disso
- cachear DTOs compactos ou respostas normalizadas
- separar cache de metadata/quota do cache de resultados

### Beneficios

- menor uso de memoria
- menos risco de cache incorreto
- base pronta para filtros v2

## Prioridade 6: Enxugar o SSE inicial

### Proposta

- reduzir o primeiro payload para um resumo e os primeiros itens
- manter o restante sob paginação
- considerar reduzir `MAX_BREACH_SERIALIZE` de 200 para 50 ou 100
- enviar `fields[]` minimos nas buscas do fluxo inicial

### Beneficios

- TTFB melhor
- menos picos de memoria
- UI mais responsiva

## Prioridade 7: Observabilidade orientada a quota e performance

### Proposta

Registrar por modulo:

- duracao
- cache hit/miss
- endpoint OathNet usado
- uso de `search_id`
- tamanho aproximado do payload recebido
- tamanho do SSE emitido

### Beneficios

- permite otimizar com dado real
- facilita identificar modulos caros
- evita "otimizacao por intuicao"

## Roadmap sugerido

## Fase 1

- propagar `search_id` em todo fluxo OathNet
- retornar `search_id` ao frontend
- ajustar paginação `/api/search/more-breaches`
- ajustar `/api/victims/search`

## Fase 2

- refatorar `_stream_search()` para usar `TaskOrchestrator` de fato
- manter dependencia serial apenas para enriquecimentos derivados

## Fase 3

- adicionar `fields[]`, `dbnames`, `filter`, `filter_id`
- reduzir payload padrao

## Fase 4

- implementar bulk search/export
- separar fluxo interativo de fluxo batch

## Ganho esperado

Se as prioridades 1, 2 e 3 forem aplicadas, o projeto tende a ganhar:

- menor latencia fim a fim nas buscas automatizadas
- menor desperdicio de quota da OathNet
- menor uso de memoria por request
- melhor base para crescer sem piorar custo operacional

## Conclusao

O projeto ja tem bons blocos de base:

- `httpx.AsyncClient` singleton
- timeout por modulo
- cache TTL
- orquestrador com semaforos

O problema e que esses blocos ainda nao estao conectados da forma mais eficiente ao contrato real da OathNet.

A melhoria de maior retorno imediato e simples de justificar tecnicamente e:

1. usar `search_id` em todo o fluxo
2. paralelizar de verdade via `TaskOrchestrator`
3. reduzir campos trafegados usando `fields[]` e filtros v2

Essas tres mudancas atacam ao mesmo tempo performance, quota e escalabilidade.
