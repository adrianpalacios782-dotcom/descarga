from dataclasses import dataclass
import re

from src.domain.exceptions.domain_exceptions import InvalidUpdateInfoError

# Formato estricto SemVer: MAJOR.MINOR.PATCH (componentes enteros no negativos).
# Se tolera un prefijo "v"/"V" porque es la convención habitual en tags de Git.
_SEMVER_RE = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$", re.IGNORECASE)


@dataclass(frozen=True)
class SemanticVersion:
    """Value Object inmutable que representa una versión SemVer MAJOR.MINOR.PATCH.

    Rechaza explícitamente formatos inválidos ("1.0", "1.0.0.0", "abc",
    negativos, vacío, None). Implementa orden total para poder decidir si una
    versión remota es estrictamente superior a la local (nunca downgrade).
    """

    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        for name in ("major", "minor", "patch"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise InvalidUpdateInfoError(
                    f"Componente de versión '{name}' inválido: {value!r}"
                )

    @classmethod
    def parse(cls, raw: object) -> "SemanticVersion":
        """Construye desde una cadena tipo '1.2.3' o 'v1.2.3'.

        Lanza InvalidUpdateInfoError si el formato no es SemVer estricto.
        """
        if not isinstance(raw, str):
            raise InvalidUpdateInfoError("La versión debe ser una cadena de texto.")
        cleaned = raw.strip()
        match = _SEMVER_RE.match(cleaned)
        if not match:
            raise InvalidUpdateInfoError(f"Versión con formato inválido: {raw!r}")
        major, minor, patch = (int(g) for g in match.groups())
        return cls(major=major, minor=minor, patch=patch)

    def as_tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return self.as_tuple() < other.as_tuple()

    def __le__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return self.as_tuple() <= other.as_tuple()

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return self.as_tuple() > other.as_tuple()

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return self.as_tuple() >= other.as_tuple()
