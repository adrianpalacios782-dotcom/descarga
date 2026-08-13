import logging
from threading import Lock
from typing import Callable, Dict, List, Type, TypeVar

from src.domain.events.domain_events import DomainEvent

E = TypeVar("E", bound=DomainEvent)
EventHandler = Callable[[E], None]

logger = logging.getLogger(__name__)


class InProcessEventBus:
    """Bus de eventos en memoria thread-safe para publicar y suscribirse a eventos de dominio."""

    def __init__(self) -> None:
        self._subscribers: Dict[Type[DomainEvent], List[Callable[[DomainEvent], None]]] = {}
        self._lock = Lock()

    def subscribe(self, event_type: Type[E], handler: EventHandler[E]) -> None:
        """Registra un manejador para un tipo específico de evento."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if handler not in self._subscribers[event_type]: # type: ignore[comparison-overlap]
                self._subscribers[event_type].append(handler) # type: ignore[arg-type]

    def unsubscribe(self, event_type: Type[E], handler: EventHandler[E]) -> None:
        """Remueve un manejador previamente registrado."""
        with self._lock:
            if event_type in self._subscribers and handler in self._subscribers[event_type]: # type: ignore[comparison-overlap]
                self._subscribers[event_type].remove(handler) # type: ignore[arg-type]

    def publish(self, event: DomainEvent) -> None:
        """Publica un evento a todos los manejadores suscritos de forma segura."""
        event_type = type(event)
        handlers_to_call: List[Callable[[DomainEvent], None]] = []

        with self._lock:
            if event_type in self._subscribers:
                handlers_to_call = list(self._subscribers[event_type])

        for handler in handlers_to_call:
            try:
                handler(event)
            except Exception as ex:
                logger.error(
                    f"Error al procesar el evento '{event_type.__name__}' en el manejador '{handler}': {ex}",
                    exc_info=True
                )

    def clear(self) -> None:
        """Limpia todas las suscripciones registradas."""
        with self._lock:
            self._subscribers.clear()
