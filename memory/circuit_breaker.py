"""
Nexus Zenith V10.0 — Fase 3: Circuit Breaker Pattern
=====================================================
Formal 3-state circuit breaker para conexões externas (Supabase, APIs).

Estados:
- CLOSED:    Normal. Todas as requests passam.
- OPEN:      Offline. Requests bloqueadas, fallback SQLite ativo.
- HALF_OPEN: Testando. 1 request de probe para verificar reconexão.

Transições:
- CLOSED → OPEN:      Após N falhas consecutivas (threshold)
- OPEN → HALF_OPEN:   Após X segundos (recovery_timeout)
- HALF_OPEN → CLOSED: Se probe request sucede
- HALF_OPEN → OPEN:   Se probe request falha

Uso:
    cb = CircuitBreaker(name="supabase", failure_threshold=3, recovery_timeout=30)
    
    if cb.can_execute():
        try:
            result = await supabase_call()
            cb.record_success()
        except Exception:
            cb.record_failure()
            # fallback to SQLite
    else:
        # Use SQLite fallback
"""

import time
import logging
from typing import Optional

logger = logging.getLogger("CircuitBreaker")


class CircuitBreaker:
    """
    Implementação formal do Circuit Breaker Pattern.
    Thread-safe para uso em asyncio event loops.
    """
    
    # Estados
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"
    
    def __init__(self, name: str = "default",
                 failure_threshold: int = 3,
                 recovery_timeout: float = 30.0,
                 success_threshold: int = 1):
        """
        Args:
            name: Nome do circuit breaker (para logging)
            failure_threshold: Número de falhas consecutivas para abrir
            recovery_timeout: Segundos para tentar reconexão (OPEN → HALF_OPEN)
            success_threshold: Sucessos necessários em HALF_OPEN para fechar
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        # State
        self._state = self.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0
        self._last_state_change: float = time.time()
        
        # Metrics
        self._total_calls = 0
        self._total_failures = 0
        self._total_circuit_opens = 0
        
        logger.info(f"CircuitBreaker '{name}' initialized: "
                    f"threshold={failure_threshold}, recovery={recovery_timeout}s")
    
    @property
    def state(self) -> str:
        """Estado atual do circuit breaker."""
        # Auto-transition OPEN → HALF_OPEN após recovery_timeout
        if self._state == self.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._transition_to(self.HALF_OPEN)
        return self._state
    
    @property
    def is_closed(self) -> bool:
        return self.state == self.CLOSED
    
    @property
    def is_open(self) -> bool:
        return self.state == self.OPEN
    
    def _transition_to(self, new_state: str):
        """Transição de estado com logging."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()
        
        if new_state == self.OPEN:
            self._total_circuit_opens += 1
            logger.warning(f"⚡ CircuitBreaker '{self.name}': {old_state} → {new_state} "
                          f"(failures={self._failure_count}/{self.failure_threshold})")
        elif new_state == self.HALF_OPEN:
            logger.info(f"🔄 CircuitBreaker '{self.name}': {old_state} → {new_state} (probing...)")
        elif new_state == self.CLOSED:
            logger.info(f"✅ CircuitBreaker '{self.name}': {old_state} → {new_state} (recovered)")
    
    def can_execute(self) -> bool:
        """
        Verifica se uma request pode ser executada.
        
        Returns:
            True se a request deve ser tentada.
            False se deve usar fallback.
        """
        self._total_calls += 1
        current_state = self.state  # Triggers auto-transition
        
        if current_state == self.CLOSED:
            return True
        elif current_state == self.HALF_OPEN:
            return True  # Permite 1 probe request
        else:  # OPEN
            return False
    
    def record_success(self):
        """Registra uma request bem-sucedida."""
        if self._state == self.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._failure_count = 0
                self._success_count = 0
                self._transition_to(self.CLOSED)
        elif self._state == self.CLOSED:
            self._failure_count = 0  # Reset counter on success
    
    def record_failure(self):
        """Registra uma falha na request."""
        self._failure_count += 1
        self._total_failures += 1
        self._last_failure_time = time.time()
        
        if self._state == self.HALF_OPEN:
            # Probe falhou → volta para OPEN
            self._success_count = 0
            self._transition_to(self.OPEN)
        elif self._state == self.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._transition_to(self.OPEN)
    
    def get_metrics(self) -> dict:
        """Retorna métricas do circuit breaker para dashboard."""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self._failure_count,
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "total_circuit_opens": self._total_circuit_opens,
            "seconds_in_current_state": round(time.time() - self._last_state_change, 1),
            "seconds_since_last_failure": round(time.time() - self._last_failure_time, 1) if self._last_failure_time else None,
        }
    
    def force_open(self):
        """Força abertura manual (usado em testes ou emergências)."""
        self._failure_count = self.failure_threshold
        self._last_failure_time = time.time()
        self._transition_to(self.OPEN)
    
    def force_close(self):
        """Força fechamento manual (reset)."""
        self._failure_count = 0
        self._success_count = 0
        self._transition_to(self.CLOSED)
