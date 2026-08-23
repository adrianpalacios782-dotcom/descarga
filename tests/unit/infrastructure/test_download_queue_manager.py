"""Tests unitarios del gestor de cola de descargas (Parte 2).

Cubiertos, sin red real ni Qt event loop:
- Helpers puros: humanize_bytes / format_eta.
- Purga de temporales (*.part, *.ytdl, *.temp.*) con seguridad de ruta.
- Encolado secuencial, limite de concurrencia y despacho FIFO automatico.
- Senales Qt hacia la UI (progreso formateado, warning de calidad, fin, error).
- Cancelacion limpia: en cola, activa y carrera pre-despacho (huerfano cero).
- Integracion con MainViewModel (encolar/reintentar/cancelar a traves de la cola).
"""
import threading
import time
from pathlib import Path

import pytest

from src.domain.entities.download_task import DownloadState, DownloadTask
from src.domain.entities.format_option import FormatOption
from src.domain.entities.media_metadata import MediaMetadata
from src.domain.events.domain_events import (
    DownloadCancelledEvent,
    DownloadCompletedEvent,
    DownloadFailedEvent,
    DownloadProgressChangedEvent,
    DownloadQueuedEvent,
)
from src.domain.ports.download_engine import IDownloadEngine
from src.domain.value_objects.download_id import DownloadId
from src.domain.value_objects.media_id import MediaId
from src.domain.value_objects.url import Url
from src.infrastructure.adapters.download.download_queue_manager import (
    DownloadQueueManager,
    format_eta,
    humanize_bytes,
    purge_temporary_files,
)
from src.infrastructure.adapters.storage.sqlite_db import DatabaseManager
from src.infrastructure.adapters.storage.sqlite_repository import SQLiteDownloadRepository
from src.infrastructure.event_bus.in_process_event_bus import InProcessEventBus


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class BlockingFakeEngine(IDownloadEngine):
    """Motor falso: download() bloquea en su gate hasta que el test lo libere."""

    def __init__(self) -> None:
        self.downloaded: list[str] = []
        self.cancelled: list[str] = []
        self.paused: list[str] = []
        self.resumed: list[str] = []
        self.gates: dict[str, threading.Event] = {}

    def add_gate(self, task_id: str) -> None:
        self.gates[task_id] = threading.Event()

    def release(self, task_id: str) -> None:
        gate = self.gates.get(task_id)
        if gate is not None:
            gate.set()

    def download(self, task: DownloadTask) -> None:
        task_id = task.id.value
        self.downloaded.append(task_id)
        gate = self.gates.get(task_id)
        if gate is not None:
            gate.wait(timeout=10)

    def pause(self, task: DownloadTask) -> None:
        self.paused.append(task.id.value)

    def resume(self, task: DownloadTask) -> None:
        self.resumed.append(task.id.value)

    def cancel(self, task: DownloadTask) -> None:
        # El motor real publica DownloadCancelledEvent; los tests lo simulan.
        self.cancelled.append(task.id.value)


class FakePool:
    """Sustituto de QThreadPool: modo 'thread' (ejecuta en hilo daemon) o 'manual'.

    En modo 'manual' los runnables se capturan para ejecutarlos a mano y
    reproducir carreras deterministas.
    """

    def __init__(self, mode: str = "thread") -> None:
        self.mode = mode
        self.max_threads = 0
        self.captured: list[object] = []

    def setMaxThreadCount(self, threads: int) -> None:  # noqa: N802
        self.max_threads = threads

    def start(self, runnable: object) -> None:
        if self.mode == "manual":
            self.captured.append(runnable)
            return
        worker = threading.Thread(target=runnable.run, daemon=True)  # type: ignore[attr-defined]
        worker.start()


def _wait_for(predicate, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def _make_task(destination_path: str) -> DownloadTask:
    fmt = FormatOption(format_id="137", extension="mp4")
    url = Url("https://youtube.com/watch?v=123")
    media = MediaMetadata(
        media_id=MediaId.generate(),
        url=url,
        platform="YouTube",
        title="Test Stream",
        formats=[fmt],
    )
    return DownloadTask(
        id=DownloadId.generate(),
        media=media,
        selected_format=fmt,
        destination_path=destination_path,
    )


class Recorder:
    """Acumula emisiones de una senal como tuplas de argumentos."""

    def __init__(self, signal) -> None:
        self.calls: list[tuple] = []
        signal.connect(self._slot)

    def _slot(self, *args) -> None:
        self.calls.append(args)

    def ids(self) -> list[str]:
        return [c[0] for c in self.calls]


@pytest.fixture
def repo(tmp_path: Path):
    db_manager = DatabaseManager(":memory:")
    repository = SQLiteDownloadRepository(db_manager=db_manager)
    yield repository
    db_manager.close()


# ---------------------------------------------------------------------------
# HELPERS PUROS
# ---------------------------------------------------------------------------
class TestHelpersPuros:

    @pytest.mark.parametrize("value,expected", [
        (0, "0 B"),
        (512, "512 B"),
        (2048, "2.0 KB"),
        (1024 * 1024 * 1.5, "1.5 MB"),
        (1024 ** 3, "1.0 GB"),
        (None, "?"),
        (-5, "?"),
    ])
    def test_humanize_bytes(self, value, expected):
        assert humanize_bytes(value) == expected

    @pytest.mark.parametrize("seconds,expected", [
        (None, "--:--"),
        (0, "--:--"),
        (-3, "--:--"),
        (45, "0:45"),
        (125, "2:05"),
        (3675, "1:01:15"),
    ])
    def test_format_eta(self, seconds, expected):
        assert format_eta(seconds) == expected


# ---------------------------------------------------------------------------
# PURGA DE TEMPORALES
# ---------------------------------------------------------------------------
class TestPurgaTemporales:

    def test_purga_solo_residuos_y_preserva_el_archivo_final(self, tmp_path: Path):
        dest = tmp_path / "video_final.mp4"
        final = tmp_path / "video_final.mp4"
        part = tmp_path / "video_final.mp4.part"
        ytdl = tmp_path / "video_final.mp4.ytdl"
        temp = tmp_path / "video_final.temp.mp4"
        ajeno = tmp_path / "otra_descarga.mp4"
        anidado_dir = tmp_path / "sub"
        anidado_dir.mkdir()
        anidado = anidado_dir / "video_final.mp4.part"

        for archivo in (final, part, ytdl, temp, ajeno, anidado):
            archivo.write_bytes(b"x")

        eliminados = purge_temporary_files(str(dest))

        assert sorted(eliminados) == [
            "video_final.mp4.part",
            "video_final.temp.mp4",
            "video_final.mp4.ytdl",
        ] or sorted(eliminados) == sorted([
            "video_final.mp4.part",
            "video_final.temp.mp4",
            "video_final.mp4.ytdl",
        ])
        assert not part.exists()
        assert not ytdl.exists()
        assert not temp.exists()
        assert final.exists()      # el artefacto final NUNCA se borra
        assert ajeno.exists()      # archivos ajenos intactos
        assert anidado.exists()    # sin recursion fuera del alcance

    def test_destino_inexistente_no_explota(self, tmp_path: Path):
        assert purge_temporary_files(str(tmp_path / "no" / "existe.mp4")) == []


# ---------------------------------------------------------------------------
# COLA BASICA: ENCOLADO, LIMITE Y DESPACHO AUTOMATICO
# ---------------------------------------------------------------------------
class TestColaBasica:

    def _make_manager(self, engine: BlockingFakeEngine, bus: InProcessEventBus, repo,
                      max_concurrent: int = 2, pool_mode: str = "thread"):
        pool = FakePool(mode=pool_mode)
        manager = DownloadQueueManager(
            engine=engine,
            event_bus=bus,
            repository=repo,
            max_concurrent=max_concurrent,
            pool=pool,
        )
        return manager, pool

    def test_encolar_sin_slot_libre_queda_en_cola_persistido(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()

        manager, _pool = self._make_manager(engine, bus, repo, max_concurrent=1)
        bloqueadora = _make_task(str(tmp_path / "bloq.mp4"))
        engine.add_gate(bloqueadora.id.value)
        manager.enqueue(bloqueadora)

        # Suscribimos el registro DESPUÉS de la primera para aislar la tarea nueva.
        queued_events: list[DownloadQueuedEvent] = []
        bus.subscribe(DownloadQueuedEvent, queued_events.append)

        task = _make_task(str(tmp_path / "a.mp4"))
        enqueued = Recorder(manager.enqueued)

        manager.enqueue(task)

        assert task.status == DownloadState.QUEUED
        assert enqueued.ids() == [task.id.value]
        assert [e.task_id for e in queued_events] == [task.id.value]
        persistida = repo.get_by_id(task.id)
        assert persistida is not None
        assert persistida.status == DownloadState.QUEUED
        assert manager.pending_ids() == [task.id.value]

    def test_encolar_con_slot_libre_despacha_inmediatamente(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()
        manager, _pool = self._make_manager(engine, bus, repo, max_concurrent=2)

        task = _make_task(str(tmp_path / "a.mp4"))
        enqueued = Recorder(manager.enqueued)
        started = Recorder(manager.started)

        manager.enqueue(task)

        assert started.ids() == [task.id.value]
        assert _wait_for(lambda: engine.downloaded == [task.id.value])
        assert task.status == DownloadState.DOWNLOADING
        assert enqueued.ids() == [task.id.value]

    def test_limite_de_concurrencia_deja_el_resto_en_cola(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()
        manager, _pool = self._make_manager(engine, bus, repo, max_concurrent=2)

        tasks = []
        for name in ("a", "b", "c", "d"):
            task = _make_task(str(tmp_path / f"{name}.mp4"))
            engine.add_gate(task.id.value)
            tasks.append(task)
            manager.enqueue(task)

        assert sorted(manager.active_ids()) == sorted(t.id.value for t in tasks[:2])
        assert manager.pending_ids() == [tasks[2].id.value, tasks[3].id.value]
        assert _wait_for(lambda: len(engine.downloaded) == 2)
        for tarea in tasks[2:]:
            assert tarea.status == DownloadState.QUEUED
            assert repo.get_by_id(tarea.id).status == DownloadState.QUEUED

    def test_liberar_slot_despacha_automaticamente_en_orden_fifo(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()
        manager, _pool = self._make_manager(engine, bus, repo, max_concurrent=1)
        started = Recorder(manager.started)
        finished = Recorder(manager.finished)

        primera = _make_task(str(tmp_path / "p1.mp4"))
        segunda = _make_task(str(tmp_path / "p2.mp4"))
        tercera = _make_task(str(tmp_path / "p3.mp4"))
        for tarea in (primera, segunda, tercera):
            engine.add_gate(tarea.id.value)
            manager.enqueue(tarea)

        assert engine.downloaded == [primera.id.value]

        bus.publish(DownloadCompletedEvent(
            task_id=primera.id.value,
            destination_path=primera.destination_path,
            total_bytes=1024,
        ))

        assert _wait_for(lambda: len(engine.downloaded) == 2)
        assert segunda.id.value in engine.downloaded
        assert finished.calls == [(primera.id.value, primera.destination_path)]
        assert started.ids()[-1] == segunda.id.value
        assert manager.pending_ids() == [tercera.id.value]

    def test_completado_con_advertencia_emite_quality_warning_y_finished(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()
        manager, _pool = self._make_manager(engine, bus, repo, max_concurrent=1)
        warning = Recorder(manager.quality_warning)
        finished = Recorder(manager.finished)

        task = _make_task(str(tmp_path / "w.mp4"))
        engine.add_gate(task.id.value)
        manager.enqueue(task)

        bus.publish(DownloadCompletedEvent(
            task_id=task.id.value,
            destination_path=task.destination_path,
            total_bytes=2048,
            warning_message="Se solicitó 1080p pero el máximo disponible fue 720p.",
        ))

        assert warning.calls == [(task.id.value, "Se solicitó 1080p pero el máximo disponible fue 720p.")]
        assert finished.calls == [(task.id.value, task.destination_path)]
        assert manager.active_ids() == []

    def test_fallo_publica_error_y_purga_residuos(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()
        manager, _pool = self._make_manager(engine, bus, repo, max_concurrent=1)
        errors = Recorder(manager.error)

        task = _make_task(str(tmp_path / "f.mp4"))
        dest_dir = tmp_path
        residuo = dest_dir / "f.mp4.part"
        residuo.write_bytes(b"basura")
        engine.add_gate(task.id.value)
        manager.enqueue(task)

        bus.publish(DownloadFailedEvent(task_id=task.id.value, error_message="HTTP 403"))

        assert errors.calls == [(task.id.value, "HTTP 403")]
        assert not residuo.exists()
        assert manager.active_ids() == []

    def test_progreso_se_emite_formateado_para_la_ui(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()
        manager, _pool = self._make_manager(engine, bus, repo, max_concurrent=1)
        progress = Recorder(manager.progress)

        task = _make_task(str(tmp_path / "p.mp4"))
        engine.add_gate(task.id.value)
        manager.enqueue(task)

        bus.publish(DownloadProgressChangedEvent(
            task_id=task.id.value,
            progress_percent=50.0,
            downloaded_bytes=512,
            total_bytes=1024,
            speed_bps=2048.0,
            eta_seconds=45.0,
        ))

        assert progress.calls == [
            (task.id.value, 50.0, 2048.0, "0:45", "512 B", "1.0 KB")
        ]

    def test_evento_tardio_tras_cierre_se_ignora(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()
        manager, _pool = self._make_manager(engine, bus, repo, max_concurrent=1)
        finished = Recorder(manager.finished)

        task = _make_task(str(tmp_path / "t.mp4"))
        engine.add_gate(task.id.value)
        manager.enqueue(task)
        completion = DownloadCompletedEvent(
            task_id=task.id.value,
            destination_path=task.destination_path,
            total_bytes=10,
        )

        bus.publish(completion)
        bus.publish(completion)  # duplicado tardío tras liberar el slot

        assert finished.calls == [(task.id.value, task.destination_path)]
        assert manager.active_ids() == []


# ---------------------------------------------------------------------------
# CANCELACION LIMPIA
# ---------------------------------------------------------------------------
class TestCancelacion:

    def _make_manager(self, engine, bus, repo, max_concurrent=1, pool_mode="thread"):
        pool = FakePool(mode=pool_mode)
        manager = DownloadQueueManager(
            engine=engine,
            event_bus=bus,
            repository=repo,
            max_concurrent=max_concurrent,
            pool=pool,
        )
        return manager, pool

    def test_cancelar_tarea_en_cola_nunca_llega_al_motor(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()
        cancelled_events: list[DownloadCancelledEvent] = []
        bus.subscribe(DownloadCancelledEvent, cancelled_events.append)
        manager, _pool = self._make_manager(engine, bus, repo, max_concurrent=1)
        cancelled_signal = Recorder(manager.cancelled)

        activa = _make_task(str(tmp_path / "act.mp4"))
        engine.add_gate(activa.id.value)
        manager.enqueue(activa)

        en_cola = _make_task(str(tmp_path / "cola.mp4"))
        manager.enqueue(en_cola)
        assert en_cola.status == DownloadState.QUEUED

        assert manager.cancel(en_cola.id.value) is True

        assert cancelled_signal.ids() == [en_cola.id.value]
        assert [e.task_id for e in cancelled_events] == [en_cola.id.value]
        assert en_cola.id.value not in engine.downloaded
        assert repo.get_by_id(en_cola.id).status == DownloadState.CANCELLED
        assert manager.pending_ids() == []

    def test_cancelar_tarea_activa_detiene_purga_y_libera_slot(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()
        manager, _pool = self._make_manager(engine, bus, repo, max_concurrent=1)
        cancelled_signal = Recorder(manager.cancelled)

        activa = _make_task(str(tmp_path / "act.mp4"))
        engine.add_gate(activa.id.value)
        manager.enqueue(activa)

        siguiente = _make_task(str(tmp_path / "sig.mp4"))
        engine.add_gate(siguiente.id.value)
        manager.enqueue(siguiente)

        # Residuos preexistentes del intento actual.
        residuos = [
            tmp_path / "act.mp4.part",
            tmp_path / "act.mp4.ytdl",
            tmp_path / "act.temp.mp4",
        ]
        for residuo in residuos:
            residuo.write_bytes(b"x")

        assert manager.cancel(activa.id.value) is True
        # El motor real publica el evento de cancelacion; lo simulamos:
        bus.publish(DownloadCancelledEvent(task_id=activa.id.value))

        assert cancelled_signal.ids() == [activa.id.value]
        assert activa.id.value in engine.cancelled
        assert all(not r.exists() for r in residuos)
        assert repo.get_by_id(activa.id).status == DownloadState.CANCELLED
        # El slot liberado despacha automaticamente a la siguiente.
        assert _wait_for(lambda: siguiente.id.value in engine.downloaded)
        assert siguiente.status == DownloadState.DOWNLOADING

    def test_carrera_pre_despacho_no_deja_huerfanos(self, tmp_path, repo):
        """Cancelar entre el arranque del worker y la invocacion del motor."""
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()
        manager, pool = self._make_manager(engine, bus, repo, max_concurrent=1,
                                           pool_mode="manual")
        cancelled_signal = Recorder(manager.cancelled)

        task = _make_task(str(tmp_path / "race.mp4"))
        manager.enqueue(task)
        assert len(pool.captured) == 1          # worker capturado, aun NO ejecutado
        assert engine.downloaded == []

        assert manager.cancel(task.id.value) is True
        # El motor real publicaria el evento aunque el worker no arranco:
        bus.publish(DownloadCancelledEvent(task_id=task.id.value))
        assert cancelled_signal.ids() == [task.id.value]

        # Ahora el worker capturado se ejecuta: debe salir sin llamar al motor.
        pool.captured[0].run()

        assert engine.downloaded == []           # huerfano cero
        assert repo.get_by_id(task.id).status == DownloadState.CANCELLED

    def test_cancelar_id_desconocido_devuelve_false(self, repo):
        engine = BlockingFakeEngine()
        manager, _pool = self._make_manager(engine, InProcessEventBus(), repo)
        assert manager.cancel("id-inexistente") is False

    def test_pausa_y_reanudacion_delegan_solo_en_activas(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        manager, _pool = self._make_manager(engine, InProcessEventBus(), repo)

        activa = _make_task(str(tmp_path / "a.mp4"))
        engine.add_gate(activa.id.value)
        manager.enqueue(activa)

        assert manager.pause(activa.id.value) is True
        assert engine.paused == [activa.id.value]
        assert manager.resume(activa.id.value) is True
        assert engine.resumed == [activa.id.value]
        assert manager.pause("desconocida") is False


# ---------------------------------------------------------------------------
# LIMITE DE CONCURRENCIA EN CALIENTE Y VALIDACIONES
# ---------------------------------------------------------------------------
class TestConcurrenciaDinamica:

    def test_subir_el_limite_despacha_pendientes(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        manager, pool = TestColaBasica()._make_manager(
            engine, InProcessEventBus(), repo, max_concurrent=1
        )

        primera = _make_task(str(tmp_path / "1.mp4"))
        segunda = _make_task(str(tmp_path / "2.mp4"))
        engine.add_gate(primera.id.value)
        engine.add_gate(segunda.id.value)
        manager.enqueue(primera)
        manager.enqueue(segunda)
        assert manager.pending_ids() == [segunda.id.value]

        manager.set_max_concurrent(2)

        assert _wait_for(lambda: len(engine.downloaded) == 2)
        assert pool.max_threads == 2
        assert manager.pending_ids() == []

    def test_bajar_el_limite_no_aborta_activas(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        manager, _pool = TestColaBasica()._make_manager(
            engine, InProcessEventBus(), repo, max_concurrent=2
        )

        tareas = []
        for name in ("x", "y"):
            tarea = _make_task(str(tmp_path / f"{name}.mp4"))
            engine.add_gate(tarea.id.value)
            tareas.append(tarea)
            manager.enqueue(tarea)

        manager.set_max_concurrent(1)

        assert sorted(manager.active_ids()) == sorted(t.id.value for t in tareas)
        assert engine.cancelled == []
        assert manager.max_concurrent == 1

    @pytest.mark.parametrize("valor", [0, -1])
    def test_limite_invalido_rechazado(self, valor, repo):
        with pytest.raises(ValueError):
            DownloadQueueManager(
                engine=BlockingFakeEngine(),
                event_bus=InProcessEventBus(),
                repository=repo,
                max_concurrent=valor,
            )

    def test_enqueue_duplicado_es_idempotente(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        manager, _pool = TestColaBasica()._make_manager(
            engine, InProcessEventBus(), repo, max_concurrent=1
        )

        bloqueadora = _make_task(str(tmp_path / "b.mp4"))
        engine.add_gate(bloqueadora.id.value)
        manager.enqueue(bloqueadora)

        tarea = _make_task(str(tmp_path / "t.mp4"))
        manager.enqueue(tarea)
        manager.enqueue(tarea)  # segunda vez: ignorada

        assert manager.pending_ids() == [tarea.id.value]

    def test_enqueue_de_tarea_terminal_rechazado(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        manager, _pool = TestColaBasica()._make_manager(
            engine, InProcessEventBus(), repo, max_concurrent=2
        )

        tarea = _make_task(str(tmp_path / "done.mp4"))
        tarea.transition_to(DownloadState.DOWNLOADING)
        tarea.complete()
        assert tarea.status == DownloadState.COMPLETED

        with pytest.raises(ValueError):
            manager.enqueue(tarea)


# ---------------------------------------------------------------------------
# INTEGRACION CON MAINVIEWMODEL
# ---------------------------------------------------------------------------
class TestIntegracionViewModel:

    def _build_vm(self, repo, engine, bus, queue=None):
        from src.presentation.view_models.main_view_model import MainViewModel

        class _NoopAdapter:
            pass

        return MainViewModel(
            platform_adapter=_NoopAdapter(),   # solo se usa para analizar URLs
            download_engine=engine,
            repository=repo,
            event_bus=bus,
            download_queue=queue,
        )

    def _media(self):
        fmt = FormatOption(format_id="137", extension="mp4")
        url = Url("https://youtube.com/watch?v=xyz")
        return MediaMetadata(
            media_id=MediaId.generate(), url=url, platform="YouTube",
            title="VM Stream", formats=[fmt],
        ), fmt

    def test_create_and_start_encola_a_traves_de_la_cola(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()
        manager, _pool = TestColaBasica()._make_manager(engine, bus, repo, max_concurrent=2)
        vm = self._build_vm(repo, engine, bus, queue=manager)

        media, fmt = self._media()
        created = Recorder(vm.download_created)
        queued = Recorder(vm.download_queued)
        started = Recorder(vm.download_started)

        task = vm.create_and_start_download(media, fmt.format_id, str(tmp_path / "vm.mp4"))

        assert [c[0].id.value for c in created.calls] == [task.id.value]
        assert queued.ids() == [task.id.value]     # paso por "En cola"
        assert started.ids() == [task.id.value]    # despachada al haber slot
        assert _wait_for(lambda: engine.downloaded == [task.id.value])

    def test_retry_reencola_y_despacha(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()
        manager, _pool = TestColaBasica()._make_manager(engine, bus, repo, max_concurrent=2)
        vm = self._build_vm(repo, engine, bus, queue=manager)

        media, fmt = self._media()
        task = vm.create_and_start_download(media, fmt.format_id, str(tmp_path / "r.mp4"))
        task.fail("boom")
        repo.save(task)
        assert repo.get_by_id(task.id).status == DownloadState.FAILED
        # El motor real publica el fallo; la cola libera el slot del intento #1.
        bus.publish(DownloadFailedEvent(task_id=task.id.value, error_message="boom"))

        vm.retry_download(task.id.value)

        # La cola opera sobre la copia persistida; el objeto local queda FAILED.
        persistida = repo.get_by_id(task.id)
        assert persistida is not None
        assert persistida.status == DownloadState.DOWNLOADING
        assert _wait_for(lambda: engine.downloaded.count(task.id.value) == 2)

    def test_cancel_ruta_por_la_cola(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()
        manager, _pool = TestColaBasica()._make_manager(engine, bus, repo, max_concurrent=1)
        vm = self._build_vm(repo, engine, bus, queue=manager)

        media, fmt = self._media()
        ocupada = vm.create_and_start_download(media, fmt.format_id, str(tmp_path / "o.mp4"))
        engine.add_gate(ocupada.id.value)

        en_cola_media, en_cola_fmt = self._media()
        en_cola = vm.create_and_start_download(
            en_cola_media, en_cola_fmt.format_id, str(tmp_path / "c.mp4")
        )
        assert en_cola.status == DownloadState.QUEUED

        vm.cancel_download(en_cola.id.value)

        assert en_cola.status == DownloadState.CANCELLED
        assert en_cola.id.value not in engine.downloaded

    def test_sin_cola_conserva_comportamiento_legacy(self, tmp_path, repo):
        engine = BlockingFakeEngine()
        bus = InProcessEventBus()
        vm = self._build_vm(repo, engine, bus, queue=None)

        media, fmt = self._media()
        task = vm.create_and_start_download(media, fmt.format_id, str(tmp_path / "l.mp4"))

        # Sin cola, StartDownloadUseCase dispara el motor directamente.
        assert _wait_for(lambda: engine.downloaded == [task.id.value])
        persistida = repo.get_by_id(task.id)
        assert persistida is not None
        assert persistida.status == DownloadState.DOWNLOADING
