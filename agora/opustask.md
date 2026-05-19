 veja C:\Users\vtbit\Documents\nexus_osint\agora  leia o readme.md Revise os dois plannings com base na avaliação
  crítica do Codex.

  Foco obrigatório:
  - Trabalhar apenas R0/R1 agora
  - Contratos primeiro
  - Adapter legacy para /api/search
  - ConnectorResult schema
  - Status 8-state
  - Decisão de privacidade para search_events
  - Job store mínimo
  - UI preparada, sem métricas fake
  - Probes sensíveis apenas lab-only/compliance gate
  - Signal v2 continua como UX principal
  - Graphite & Ember continua como linguagem visual
  - Casebook continua para exports/PDF/dossiês

  Não discuta agora:
  - graph avançado
  - marketplace
  - billing
  - multi-tenancy
  - probes cinza
  - Source Health real
  - Jobs Queue completa
  - cases persistentes completos

  Entregue uma revisão enxuta e implementável para R0/R1, com tarefas em ordem, arquivos prováveis, contratos JSON e
  critérios de aceite.  codex disse:
  • Revisei e corrigi os dois plannings:

    - .planning/REAL_TIME_OSINT_PLAN.md:10
    - .planning/VISUAL_REDESIGN_PLAN.md:10

    Resumo Executivo
    Planos fazem sentido juntos, mas antigo estava grande demais. Backend queria motor real-time + job store + novos
    probes sensíveis + métricas admin no mesmo MVP. Frontend queria telas que dependem disso antes do backend existir.
    Corrigi: contrato primeiro, adapters seguros, UI preparada, probes arriscados só lab/compliance.

    Notas
    | Critério | Nota |
    |---|---:|
    | Real-time OSINT | 6.0/10 |
    | Visual/frontend | 7.5/10 |
    | Compatibilidade | 7.0/10 |
    | Implementabilidade repo atual | 6.0/10 |
    | Risco técnico | 7.5/10 alto |
    | Clareza UX | 7.5/10 |
    | Originalidade visual | 8.0/10 |
    | Preparo real-time | 8.0/10 |
    | Segurança/compliance | 5.5/10 |
    | Prioridade fases | 6.0/10 |

    Pontos Fortes

    - Direção produto certa: investigação/workspace, não search bar genérico.
    - ConnectorCard + Evidence + Confidence = bom eixo premium.
    - Postgres/Redis atual sustenta job/event store melhor que SQLite antigo.
    - Visual evita OathNet clone melhor que UI atual.

    Pontos Fracos / Conflitos

    - likely virava found; isso quebra anti-FP. Corrigido para status 8-state.
    - Source Health/Jobs/Queue dependiam de backend inexistente. Agora esperam connector_metrics/search_jobs.
    - Forgot-password, WhatsApp, Telegram, Truecaller, HIBP estavam cedo demais. Agora lab-only/compliance gate.
    - Landing/rename de index.html cedo demais arriscava auth atual. Agora adiado.

    Implementar Primeiro

    1. ConnectorResult schema + status 8-state.
    2. Adapter legacy para /api/search atual.
    3. Visual tokens + shell + ConnectorCard/StatusPill/Evidence empty state.
    4. Decisão privacidade para search_events.
    5. Depois search_v2 + job_store + SSE replay.

    Adiar

    - Source Health real.
    - Jobs & Queue.
    - Cancel/retry real.
    - Cases persistentes.
    - Chain graph.
    - Probes externos sensíveis.

    Remover/Simplificar

    - Mock production-like em admin/live.
    - CDN para Lit.
    - Frontend decidindo permissão.
    - Truecaller do roadmap default.
    - Deprecar /api/search cedo.

    Perguntas Bloqueantes

    - search_events: hash-only TTL 7d ou payload criptografado?
    - Gravatar no MVP: permitido enviar MD5 de email a terceiro?
    - HIBP: comprar key + ToS/disclosure ou fora?
    - Quórum final: ≥2 fontes ou 1 hard_positive ≥90?
    - Quando aceitar mudança visual final da brand?

    Recomendação Opus
    Opus deve revisar agora só R0/R1: contrato, privacidade, adapters, job store mínimo. Não discutir graph,
  marketplace,
    billing, multi-tenancy ou probes cinza ainda.

    Verificação: docs only; não rodei testes.
