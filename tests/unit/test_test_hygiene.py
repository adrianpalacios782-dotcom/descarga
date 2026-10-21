"""Higiene de las pruebas: `time.sleep` no se puede parchear globalmente.

ANTIPATRÓN (causa de los timeouts flaky en GitHub Actions):

    time.sleep = lambda *_: None      # parche GLOBAL del módulo `time`

Ese parche sobrevive al test que lo hizo y convierte cualquier bucle de sondeo
con `time.sleep(...)` en un *busy-wait* que satura una CPU. Como la descarga
corre en un hilo de trabajo, en un runner lento (2 vCPU de GitHub Actions) el
sondeo roba CPU al hilo de descarga y el test falla por timeout, aunque el
código de producción sea correcto. En local (varias CPUs) pasa siempre: es
flakiness pura, no un fallo funcional.

Este archivo fija las dos defensas:

1. `_wait_for` de los tests de integracion espera con `threading.Event.wait()`
   (bloqueo real del SO), no con `time.sleep`: no gira en busy-wait y no se ve
   afectado por un parche global de `time.sleep`.
2. Un fixture autouse de `tests/conftest.py` restaura `time.sleep` tras cada
   test, de modo que un parche global solo afecta al test que lo hizo.
"""

import time
from typing import Callable

import pytest

from tests.integration.test_download_engine import _wait_for as _wait_for_engine
from tests.integration.test_time_range_download import _wait_for as _wait_for_range

# Sleep original capturado en tiempo de importacion (antes de que ningun test
# tenga oportunidad de parchearlo).
_ORIGINAL_SLEEP = time.sleep


@pytest.mark.parametrize(
    "wait_for",
    [_wait_for_engine, _wait_for_range],
    ids=["download_engine", "time_range_download"],
)
def test_wait_for_ignora_un_time_sleep_parcheado(
    monkeypatch: pytest.MonkeyPatch,
    wait_for: Callable[..., bool],
) -> None:
    """`_wait_for` no debe usar el `time.sleep` parcheado globalmente."""
    parcheadas: list[int] = []
    monkeypatch.setattr(time, "sleep", lambda *_: parcheadas.append(1))

    estado = {"n": 0}

    def predicado() -> bool:
        estado["n"] += 1
        return estado["n"] >= 3

    assert wait_for(predicado, timeout=5.0) is True
    assert parcheadas == [], (
        "_wait_for uso el time.sleep parcheado: el sondeo se vuelve busy-wait y "
        "roba CPU al hilo de descarga (timeouts flaky en runners de 2 vCPU)"
    )


def test_a_parche_global_de_time_sleep() -> None:
    """Reproduce el antipatron a proposito (el fixture autouse lo revierte)."""
    time.sleep = lambda *_: None  # type: ignore[assignment]
    assert time.sleep is not _ORIGINAL_SLEEP


def test_b_el_parche_global_fue_restaurado() -> None:
    """El fixture autouse de conftest.py restaura `time.sleep` tras cada test."""
    assert time.sleep is _ORIGINAL_SLEEP, (
        "time.sleep quedo parcheado globalmente: un test anterior no lo restauro"
    )
