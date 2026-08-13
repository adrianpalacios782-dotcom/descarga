from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class DownloadId:
    """Value Object inmutable que representa el identificador único de una tarea de descarga."""
    value: str

    def __post_init__(self) -> None:
        if not self.value or not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("DownloadId debe ser una cadena de texto no vacía.")

    @classmethod
    def generate(cls) -> "DownloadId":
        """Genera un nuevo DownloadId basado en UUIDv4."""
        return cls(value=str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value
