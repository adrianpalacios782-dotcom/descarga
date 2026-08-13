from dataclasses import dataclass
import hashlib
import uuid


@dataclass(frozen=True)
class MediaId:
    """Value Object inmutable que representa el identificador único de un contenido multimedia."""
    value: str

    def __post_init__(self) -> None:
        if not self.value or not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("MediaId debe ser una cadena de texto no vacía.")

    @classmethod
    def generate(cls) -> "MediaId":
        """Genera un MediaId aleatorio."""
        return cls(value=str(uuid.uuid4()))

    @classmethod
    def from_string(cls, identifier: str) -> "MediaId":
        """Crea un MediaId determinista basado en un identificador o hash de URL."""
        hashed = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:16]
        return cls(value=f"media_{hashed}")

    def __str__(self) -> str:
        return self.value
