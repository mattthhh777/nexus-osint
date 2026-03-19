"""
src/core/quota_guardian.py
==========================
PASSO 4 — A Ideia Extra Profissional: Guardião de Cota

Por que isso existe?
  Você tem 100 lookups/dia no plano Starter da OathNet.
  Sem controle, é fácil esgotar a cota sem perceber — especialmente
  com múltiplos usuários, testes ou buscas pesadas.

  Este módulo resolve isso com 3 camadas de proteção:

  Camada 1 — CONTADOR LOCAL:
    Rastreia quantos lookups você usou hoje, mesmo antes de chamar a API.
    Se você já usou 95/100, avisa com um banner amarelo antes da busca.

  Camada 2 — ESTIMATIVA DE CUSTO:
    Antes de rodar, calcula "esta busca vai custar X lookups".
    Se custaria mais do que você tem, pergunta se quer continuar.

  Camada 3 — SYNC COM API:
    Após cada busca bem-sucedida, sincroniza o contador com os dados
    reais da API (oath_result.meta.used_today).

Como usar no app.py:
  from src.core.quota_guardian import QuotaGuardian

  guardian = QuotaGuardian.load()        # carrega do disco

  # Antes de buscar:
  can_search, warning_msg = guardian.can_run(config)
  if not can_search:
      st.error(warning_msg)
      return

  # Depois de buscar (sincroniza com API real):
  if results.oath_result and results.oath_result.meta.used_today:
      guardian.sync_from_api(results.oath_result.meta)
      guardian.save()
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("nexusosint.quota")

# Arquivo onde salvamos o estado da cota (fora do git!)
QUOTA_FILE = Path(".quota_state.json")

# Custo estimado de cada módulo em lookups
MODULE_COSTS: dict[str, int] = {
    "run_breach":    1,   # 1 lookup por busca de breach
    "run_stealer":   1,   # 1 lookup por busca de stealer
    "run_holehe":    1,   # 1 lookup
    "run_ghunt":     1,   # 1 lookup
    "run_discord":   1,   # 1 lookup
    "run_steam":     0,   # não consome cota OathNet (API pública Steam)
    "run_xbox":      0,   # não consome cota OathNet
    "run_roblox":    0,   # não consome cota OathNet
    "run_ip":        1,   # 1 lookup
    "run_subdomain": 1,   # 1 lookup
    "run_sherlock":  0,   # não consome cota OathNet (checks HTTP direto)
}


@dataclass
class QuotaState:
    """Estado atual da cota."""
    used_today:    int  = 0
    daily_limit:   int  = 100       # padrão plano Starter
    is_unlimited:  bool = False
    plan:          str  = "starter"
    last_reset:    str  = ""        # data do último reset (YYYY-MM-DD)
    last_sync:     str  = ""        # quando sincronizamos com a API pela última vez

    @property
    def remaining(self) -> int:
        if self.is_unlimited:
            return 999
        return max(0, self.daily_limit - self.used_today)

    @property
    def usage_pct(self) -> float:
        if self.is_unlimited or self.daily_limit == 0:
            return 0.0
        return min(self.used_today / self.daily_limit * 100, 100.0)

    @property
    def status_color(self) -> str:
        """Cor para exibir na UI baseada no uso."""
        pct = self.usage_pct
        if pct >= 90: return "#f85149"    # vermelho — crítico
        if pct >= 70: return "#f0883e"    # laranja — aviso
        if pct >= 50: return "#ffd700"    # amarelo — atenção
        return "#39d353"                   # verde — OK

    @property
    def status_icon(self) -> str:
        pct = self.usage_pct
        if pct >= 90: return "🔴"
        if pct >= 70: return "🟠"
        if pct >= 50: return "🟡"
        return "🟢"


class QuotaGuardian:
    """
    Gerencia e protege a cota da API OathNet.

    Garante que você nunca exceda seu limite diário acidentalmente,
    com avisos progressivos e estimativas de custo antes de cada busca.
    """

    def __init__(self, state: QuotaState) -> None:
        self._state = state
        self._reset_if_new_day()

    # ── Carregamento / salvamento ─────────────────────────────────────────

    @classmethod
    def load(cls) -> "QuotaGuardian":
        """Carrega o estado salvo do disco. Se não existir, cria do zero."""
        if QUOTA_FILE.exists():
            try:
                raw = json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
                state = QuotaState(**raw)
                logger.debug("Quota state loaded: %s/%s used", state.used_today, state.daily_limit)
                return cls(state)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("Could not load quota state: %s — starting fresh", exc)

        return cls(QuotaState(last_reset=str(date.today())))

    def save(self) -> None:
        """Salva o estado atual no disco."""
        try:
            data = {
                "used_today":   self._state.used_today,
                "daily_limit":  self._state.daily_limit,
                "is_unlimited": self._state.is_unlimited,
                "plan":         self._state.plan,
                "last_reset":   self._state.last_reset,
                "last_sync":    self._state.last_sync,
            }
            QUOTA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not save quota state: %s", exc)

    # ── Lógica principal ──────────────────────────────────────────────────

    def _reset_if_new_day(self) -> None:
        """Reseta o contador se estamos em um novo dia."""
        today = str(date.today())
        if self._state.last_reset != today:
            logger.info("New day — resetting quota counter (was %d)", self._state.used_today)
            self._state.used_today = 0
            self._state.last_reset = today
            self.save()

    def estimate_cost(self, config: object) -> int:
        """
        Estima quantos lookups uma busca vai consumir.

        Parâmetro: config — um SearchConfig do search_engine.py

        Retorna: número inteiro de lookups estimados
        """
        cost = 0
        for attr, lookup_cost in MODULE_COSTS.items():
            if getattr(config, attr, False):
                cost += lookup_cost
        return cost

    def can_run(self, config: object) -> tuple[bool, str]:
        """
        Verifica se há cota suficiente para rodar a busca.

        Retorna:
          (True, "")               → pode rodar
          (True, "aviso: X%")      → pode rodar, mas avisa
          (False, "erro: sem cota")→ não pode rodar
        """
        if self._state.is_unlimited:
            return True, ""

        cost      = self.estimate_cost(config)
        remaining = self._state.remaining
        from datetime import datetime, timezone
        reset_hour = 24 - datetime.now(timezone.utc).hour

        # Sem cota — bloqueado
        if remaining == 0:
            return False, (
                f"❌ **Cota esgotada hoje.** "
                f"Seus {self._state.daily_limit} lookups diários foram usados. "
                f"Reinicia em ~{reset_hour}h (meia-noite UTC). "
                f"[Ver planos](https://oathnet.org/pricing)"
            )

        # Custo maior que o disponível
        if cost > remaining:
            return False, (
                f"❌ **Lookups insuficientes.** "
                f"Esta busca precisa de ~{cost} lookup(s), "
                f"mas você tem apenas {remaining} restante(s) hoje. "
                f"Reinicia em ~{reset_hour}h."
            )

        # Aviso de 90%+ (mas ainda pode rodar)
        if self._state.usage_pct >= 90:
            return True, (
                f"⚠️ **Apenas {remaining} lookups restantes hoje** "
                f"({self._state.usage_pct:.0f}% usado). "
                f"Esta busca vai usar ~{cost}. Reinicia em ~{reset_hour}h."
            )

        # Aviso de 70%+
        if self._state.usage_pct >= 70:
            return True, (
                f"🟡 {self._state.used_today}/{self._state.daily_limit} lookups usados hoje "
                f"(+{cost} nesta busca)."
            )

        return True, ""

    def record_usage(self, cost: int) -> None:
        """
        Registra o uso local ANTES de chamar a API.
        Se a chamada falhar depois, sync_from_api() vai corrigir.
        """
        self._state.used_today = min(
            self._state.used_today + cost,
            self._state.daily_limit,
        )
        logger.info("Quota usage recorded locally: +%d (total: %d/%d)",
                    cost, self._state.used_today, self._state.daily_limit)

    def sync_from_api(self, meta: object) -> None:
        """
        Sincroniza com os dados REAIS vindos da API OathNet.
        Sempre mais preciso do que o contador local.

        Parâmetro: meta — OathnetMeta do resultado de uma busca bem-sucedida
        """
        if not meta or not meta.plan:
            return

        old = self._state.used_today

        self._state.used_today   = meta.used_today
        self._state.daily_limit  = meta.daily_limit or self._state.daily_limit
        self._state.is_unlimited = meta.is_unlimited
        self._state.plan         = meta.plan
        self._state.last_sync    = datetime.now().isoformat()

        if old != meta.used_today:
            logger.info(
                "Quota synced from API: %d → %d/%d (plan: %s)",
                old, meta.used_today, self._state.daily_limit, meta.plan
            )

    # ── Propriedades de exposição ─────────────────────────────────────────

    @property
    def state(self) -> QuotaState:
        return self._state

    def render_widget(self) -> None:
        """Renderiza o widget de quota compacto no topo da página."""
        import streamlit as st
        from datetime import datetime, timezone

        s = self._state
        if s.is_unlimited:
            st.caption(f"🟢 Plano {s.plan.upper()} · Lookups ilimitados")
            return

        color = s.status_color
        pct   = s.usage_pct

        # Calcula quando o limite reinicia (meia-noite UTC)
        now_utc    = datetime.now(timezone.utc)
        reset_hour = 24 - now_utc.hour
        reset_msg  = f"Reinicia em ~{reset_hour}h (meia-noite UTC)"

        st.markdown(
            f"""<div style="
                display:flex; align-items:center; gap:10px;
                background:#161b22; border:1px solid #30363d;
                border-radius:8px; padding:8px 14px; margin:4px 0;
                font-size:.78rem; color:#8b949e;
            ">
                <span>{s.status_icon}</span>
                <div style="flex:1">
                    <div style="
                        background:#30363d; border-radius:999px;
                        height:6px; overflow:hidden; margin-bottom:3px;
                    ">
                        <div style="
                            width:{pct:.0f}%; height:100%;
                            background:{color}; border-radius:999px;
                        "></div>
                    </div>
                    <span>OathNet API: <b style="color:{color}">{s.used_today}</b>/{s.daily_limit} lookups usados hoje
                    · <span style="color:#8b949e;font-size:.72rem">{reset_msg}</span></span>
                </div>
                <span style="color:{color}; font-weight:700">{s.remaining} restantes</span>
            </div>""",
            unsafe_allow_html=True,
        )

        # Banner contextual baseado no estado real
        if s.remaining == 0:
            st.markdown(
                f'<div style="background:#f8514915;border:1px solid #f85149;'
                f'border-radius:6px;padding:8px 12px;color:#f85149;font-size:.8rem;margin:4px 0">'
                f'🚨 <b>Cota esgotada.</b> Nenhum lookup disponível hoje. {reset_msg}. '
                f'<a href="https://oathnet.org/pricing" target="_blank" style="color:#f85149">Fazer upgrade →</a></div>',
                unsafe_allow_html=True,
            )
        elif pct >= 90:
            st.markdown(
                f'<div style="background:#f0883e15;border:1px solid #f0883e;'
                f'border-radius:6px;padding:8px 12px;color:#f0883e;font-size:.8rem;margin:4px 0">'
                f'⚠️ Apenas <b>{s.remaining} lookups restantes</b> hoje. {reset_msg}.</div>',
                unsafe_allow_html=True,
            )