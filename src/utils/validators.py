"""
src/utils/validators.py
=======================
Sanitização e classificação de todos os inputs do usuário.

Por que isso existe?
  Antes, o query do usuário ia direto para a API sem nenhuma verificação.
  Isso causava erros obscuros (ex: Steam recebendo um email) e
  abria brechas para injeção de comandos.

Como usar:
  from src.utils.validators import validate_query, QueryResult

  result = validate_query("bictoftw")
  if result.valid:
      _run_search(result.cleaned, result.query_type)
  else:
      st.error(result.error)
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Literal

# Tipos possíveis de query — usados para decidir quais módulos rodar
QueryType = Literal["email", "ip", "discord_id", "domain", "username", "phone"]


@dataclass(frozen=True)
class QueryResult:
    """
    Resultado da validação de um input.
    
    Atributos:
        valid       — True se o input é aceitável para usar
        query_type  — que tipo de dado é ("email", "ip", etc.)
        cleaned     — versão limpa e normalizada do input
        error       — mensagem de erro se valid=False
        confidence  — 0.0-1.0: quão certo estamos do tipo detectado
    """
    valid: bool
    query_type: QueryType
    cleaned: str
    error: str = ""
    confidence: float = 1.0


# ── Regexes compilados (compilar uma vez, reusar sempre — mais rápido) ────────

_RE_EMAIL      = re.compile(r'^[\w.+\-]+@[\w\-]+\.[\w.]{2,}$', re.IGNORECASE)
_RE_IPV4       = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$')
_RE_DISCORD    = re.compile(r'^\d{14,19}$')
_RE_DOMAIN     = re.compile(
    r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
)
_RE_PHONE      = re.compile(r'^\+\d{7,15}$')
# Caracteres perigosos para injeção de comandos shell
_RE_SHELL_INJECT = re.compile(r'[;&|`$<>{}\\]')


def validate_query(raw: str) -> QueryResult:
    """
    Valida, sanitiza e classifica um query do usuário.
    
    Passos internos:
      1. Remove espaços nas pontas
      2. Verifica se não está vazio
      3. Remove caracteres de injeção de shell
      4. Escapa HTML para evitar XSS se for exibido na UI
      5. Classifica o tipo automaticamente
    
    Exemplos:
        validate_query("user@example.com")  → tipo "email"
        validate_query("192.168.0.1")       → tipo "ip"
        validate_query("352826996163739666") → tipo "discord_id"
        validate_query("example.com")       → tipo "domain"
        validate_query("+5511999999999")    → tipo "phone"
        validate_query("bictoftw")          → tipo "username"
    """
    # ── Passo 1: normalização básica ──────────────────────────────────────
    q = raw.strip()
    
    # ── Passo 2: verificações de comprimento ──────────────────────────────
    if not q:
        return QueryResult(False, "username", "", "Query não pode estar vazio.")
    
    if len(q) < 2:
        return QueryResult(False, "username", q, "Query muito curto (mínimo 2 caracteres).")
    
    if len(q) > 320:
        # 320 = tamanho máximo de um email válido
        return QueryResult(False, "username", q[:320], "Query muito longo (máximo 320 caracteres).")
    
    # ── Passo 3: remover injeção de comandos shell ─────────────────────────
    # Exemplos perigosos: "user; rm -rf /", "$(whoami)", "user`id`"
    cleaned = _RE_SHELL_INJECT.sub('', q)
    if cleaned != q:
        # Avisamos que removemos caracteres, mas continuamos
        pass  # (poderia logar aqui)
    
    # ── Passo 4: escape HTML básico ────────────────────────────────────────
    # Evita que se alguém digitar "<script>alert(1)</script>" isso seja
    # renderizado como HTML em algum lugar
    cleaned = html.escape(cleaned, quote=True)
    # Mas para emails e usernames queremos o @ e o . de volta
    cleaned = cleaned.replace("&#x27;", "'").replace("&amp;", "&")
    
    # ── Passo 5: detectar tipo ─────────────────────────────────────────────
    q_type, confidence = _detect_type(cleaned)
    
    return QueryResult(
        valid=True,
        query_type=q_type,
        cleaned=cleaned,
        confidence=confidence,
    )


def _detect_type(q: str) -> tuple[QueryType, float]:
    """
    Tenta identificar o tipo do query com nível de confiança.
    Ordem de prioridade: mais específico primeiro.
    """
    # Discord ID: apenas dígitos, 14-19 caracteres
    # (tem que vir antes de "phone" pois ambos são numéricos)
    if _RE_DISCORD.match(q):
        return "discord_id", 0.95  # 95% — pode ser um número comum grande
    
    # Telefone no formato internacional: +55119...
    if _RE_PHONE.match(q):
        return "phone", 0.99
    
    # Email: tem @ e ponto depois
    if _RE_EMAIL.match(q):
        return "email", 0.99
    
    # IP v4: 4 grupos de dígitos separados por ponto
    m = _RE_IPV4.match(q)
    if m:
        # Valida se cada octeto está em 0-255
        octets = [int(m.group(i)) for i in range(1, 5)]
        if all(0 <= o <= 255 for o in octets):
            return "ip", 0.99
    
    # Domínio: tem ponto mas não é IP nem email
    if _RE_DOMAIN.match(q) and "@" not in q:
        return "domain", 0.90
    
    # Fallback: username genérico
    return "username", 0.80


def is_safe_for_api(q: str) -> bool:
    """
    Verificação rápida para usar antes de chamar qualquer API.
    Retorna False se o input parece malicioso.
    """
    dangerous_patterns = [
        r'<script',
        r'javascript:',
        r'data:text/html',
        r'\.\./\.\.',  # path traversal
        r'%00',        # null byte
    ]
    q_lower = q.lower()
    return not any(re.search(p, q_lower) for p in dangerous_patterns)


def get_display_label(query_type: QueryType) -> str:
    """Retorna um label amigável para exibir na UI."""
    labels = {
        "email":      "📧 Email",
        "ip":         "🌐 IP Address",
        "discord_id": "🎮 Discord ID",
        "domain":     "🔗 Domain",
        "phone":      "📱 Telefone",
        "username":   "👤 Username",
    }
    return labels.get(query_type, "❓ Unknown")