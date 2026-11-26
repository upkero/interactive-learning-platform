import inspect
from functools import cached_property, lru_cache
from logging import getLogger

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.app.core.clock import SystemClock
from src.app.core.settings.app import get_app_settings
from src.app.core.settings.auth import AuthSettings, get_auth_settings
from src.app.core.settings.celery import get_celery_settings
from src.app.core.settings.embeddings import EmbeddingsSettings, get_embeddings_settings
from src.app.core.settings.ingest import IngestSettings, get_ingest_settings
from src.app.core.settings.llm import CheapLLMSettings, LLMSettings, get_cheap_llm_settings, get_llm_settings
from src.app.core.settings.processing import ProcessingSettings, get_processing_settings
from src.app.core.settings.progress import get_progress_settings
from src.app.core.settings.quota import QuotaSettings, get_quota_settings
from src.app.core.settings.reports import ReportsSettings, get_reports_settings
from src.app.core.settings.smtp import get_smtp_settings
from src.app.core.settings.solver import SolverSettings, get_solver_settings
from src.app.core.settings.storage import get_storage_settings
from src.app.core.settings.upload import get_upload_settings
from src.app.db.parsing_lease import PostgresParsingLease
from src.app.db.session import build_engine, build_session_factory
from src.app.embeddings.factory import get_embedder
from src.app.ingest.images import ImageStore
from src.app.ingest.parsers.base import DocumentParser as IngestDocumentParser
from src.app.ingest.parsers.base import ParserRegistry
from src.app.ingest.parsers.gdocs_importer import GDocsImporter
from src.app.ingest.parsers.markdown_parser import MarkdownParser
from src.app.ingest.part_planner import DocumentPartPlanner
from src.app.ingest.splitting import SplitLimits
from src.app.ingest.tokens import get_token_counter
from src.app.interfaces.embeddings.embedding_service import EmbeddingServiceInterface
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.interfaces.observability.metrics_collector import MetricsCollector
from src.app.interfaces.services.part_pipeline import PartPipeline
from src.app.interfaces.storage.object_storage_client import ObjectStorageClient
from src.app.llm.factory import create_llm_client
from src.app.llm.instrumented_llm_client import InstrumentedLLMClient
from src.app.observability.decision_log import DecisionLog
from src.app.observability.notification_claims import RedisNotificationClaims
from src.app.observability.progress_notifier import RedisProgressNotifier
from src.app.observability.prometheus_metrics_collector import PrometheusMetricsCollector
from src.app.repositories.document_part_repository import DocumentPartRepository
from src.app.repositories.document_repository import DocumentRepository
from src.app.repositories.generation_ledger_repository import GenerationLedgerRepository
from src.app.repositories.image_repository import ImageRepository
from src.app.repositories.quiz_attempt_repository import QuizAttemptRepository
from src.app.repositories.report_repository import ReportRepository
from src.app.repositories.user_material_repository import UserMaterialRepository
from src.app.repositories.user_repository import UserRepository
from src.app.repositories.widget_repository import WidgetRepository
from src.app.repositories.widget_usage_repository import WidgetUsageRepository
from src.app.services.auth.auth_service import AuthService
from src.app.services.documents.document_ingest_runner import DocumentIngestRunner
from src.app.services.documents.document_ingest_service import DocumentIngestService
from src.app.services.documents.document_query_service import DocumentQueryService
from src.app.services.documents.file_inspector import FileInspector
from src.app.services.documents.generation_service import GenerationService
from src.app.services.documents.image_describer import ImageDescriber
from src.app.services.documents.import_service import ImportService
from src.app.services.documents.material_query_service import MaterialQueryService
from src.app.services.documents.part_query_service import PartQueryService
from src.app.services.documents.quiz_check_service import QuizCheckService
from src.app.services.documents.topic_segmenter import TopicSegmenter
from src.app.services.documents.upload_service import UploadService
from src.app.services.notifications.email_sender import EmailSender
from src.app.services.notifications.notification_service import NotificationService
from src.app.services.progress.progress_reader import ProgressReader
from src.app.services.quota.quota_ledger import QuotaLedger
from src.app.services.quota.quota_service import QuotaService
from src.app.services.reports.report_service import ReportService
from src.app.services.sharing.sharing_service import SharingService
from src.app.services.solver.library.library_normalizer import LibraryNormalizer
from src.app.services.solver.pipeline.part_recovery import PartRecovery
from src.app.services.solver.pipeline.stub_pipeline import StubPipeline
from src.app.services.solver.pipeline.watchdog import Watchdog
from src.app.services.solver.search.embedding_service import EmbeddingService
from src.app.services.solver.search.instrumented_embedding_service import InstrumentedEmbeddingService
from src.app.services.solver.search.widget_search import WidgetSearch
from src.app.services.users.profile_service import ProfileService
from src.app.storage.s3_object_storage_client import S3ObjectStorageClient, build_ping_client, build_s3_client
from src.app.tasks.dispatcher import CeleryTaskDispatcher


@lru_cache(maxsize=1)
def _build_docling_parser() -> IngestDocumentParser:
    from src.app.ingest.parsers.docling_parser import DoclingParser

    return DoclingParser(artifacts_path=get_ingest_settings().docling_artifacts_path)


class ApplicationContainer:
    """Composition root: the only place concrete classes are constructed."""

    # -- settings -----------------------------------------------------------

    @cached_property
    def auth_settings(self) -> AuthSettings:
        return get_auth_settings()

    @cached_property
    def processing_settings(self) -> ProcessingSettings:
        return get_processing_settings()

    @cached_property
    def ingest_settings(self) -> IngestSettings:
        return get_ingest_settings()

    @cached_property
    def reports_settings(self) -> ReportsSettings:
        return get_reports_settings()

    @cached_property
    def quota_settings(self) -> QuotaSettings:
        return get_quota_settings()

    # -- services -----------------------------------------------------------

    @cached_property
    def document_ingest_runner(self) -> DocumentIngestRunner:
        return DocumentIngestRunner(
            lease=PostgresParsingLease(self._db_engine),
            build=lambda: self.document_ingest,
            session_factory=self.session_factory,
            documents=DocumentRepository,
            notifier=self.progress_notifier,
        )

    @cached_property
    def document_ingest(self) -> DocumentIngestService:
        return DocumentIngestService(
            session_factory=self.session_factory,
            documents=DocumentRepository,
            images=ImageRepository,
            storage=self.object_storage,
            registry=ParserRegistry((_build_docling_parser(), MarkdownParser())),
            gdocs=GDocsImporter(max_bytes=get_upload_settings().max_bytes),
            parsing_lease=PostgresParsingLease(self._db_engine),
            image_store=ImageStore(self.object_storage),
            inspector=FileInspector(get_upload_settings()),
            counter=get_token_counter(),
            ingest_settings=get_ingest_settings(),
            upload_settings=get_upload_settings(),
            notifier=self.progress_notifier,
            image_describer=ImageDescriber(
                self.cheap_llm,
                max_images=get_ingest_settings().max_images,
                concurrency=get_ingest_settings().image_concurrency,
            ),
            topic_segmenter=TopicSegmenter(
                self.cheap_llm, counter=get_token_counter(), max_tokens=get_ingest_settings().segment_max_tokens
            ),
        )

    @cached_property
    def part_recovery(self) -> PartRecovery:
        return PartRecovery(
            session_factory=self.session_factory,
            parts=DocumentPartRepository,
            documents=DocumentRepository,
            ledger=self.quota_ledger,
            dispatcher=self.task_dispatcher,
            notifier=self.progress_notifier,
            users=UserRepository,
            notifications=self.notification_service,
        )

    @cached_property
    def watchdog(self) -> Watchdog:
        return Watchdog(
            session_factory=self.session_factory,
            parts=DocumentPartRepository,
            documents=DocumentRepository,
            recovery=self.part_recovery,
            dispatcher=self.task_dispatcher,
            metrics=self.metrics_collector,
            parsing_lease=PostgresParsingLease(self._db_engine),
            notifier=self.progress_notifier,
        )

    @cached_property
    def processing_pipeline(self) -> PartPipeline:
        return StubPipeline(
            session_factory=self.session_factory,
            parts=DocumentPartRepository,
            documents=DocumentRepository,
            ledger=self.quota_ledger,
            notifier=self.progress_notifier,
            users=UserRepository,
            notifications=self.notification_service,
            metrics=self.metrics_collector,
        )

    @cached_property
    def library_normalizer(self) -> LibraryNormalizer:
        return LibraryNormalizer()

    @cached_property
    def auth_service(self) -> AuthService:
        return AuthService(
            session_factory=self.session_factory,
            users=UserRepository,
            settings=self.auth_settings,
            quota_settings=self.quota_settings,
        )

    @cached_property
    def profile_service(self) -> ProfileService:
        return ProfileService(session_factory=self.session_factory, users=UserRepository)

    @cached_property
    def sharing_service(self) -> SharingService:
        return SharingService(
            session_factory=self.session_factory,
            materials=UserMaterialRepository,
            users=UserRepository,
        )

    @cached_property
    def material_query_service(self) -> MaterialQueryService:
        return MaterialQueryService(session_factory=self.session_factory, materials=UserMaterialRepository)

    @cached_property
    def quota_ledger(self) -> QuotaLedger:
        return QuotaLedger(
            users_factory=UserRepository,
            ledger_factory=GenerationLedgerRepository,
            parts_factory=DocumentPartRepository,
            clock=SystemClock(),
        )

    @cached_property
    def quota_service(self) -> QuotaService:
        return QuotaService(session_factory=self.session_factory, ledger=self.quota_ledger)

    @cached_property
    def upload_service(self) -> UploadService:
        return UploadService(
            session_factory=self.session_factory,
            inspector=FileInspector(get_upload_settings()),
            storage=self.object_storage,
            dispatcher=self.task_dispatcher,
            documents=DocumentRepository,
            materials=UserMaterialRepository,
            users=UserRepository,
            settings=self.processing_settings,
        )

    @cached_property
    def import_service(self) -> ImportService:
        return ImportService(
            session_factory=self.session_factory,
            dispatcher=self.task_dispatcher,
            documents=DocumentRepository,
            materials=UserMaterialRepository,
            users=UserRepository,
            settings=self.processing_settings,
        )

    @cached_property
    def document_query_service(self) -> DocumentQueryService:
        return DocumentQueryService(
            session_factory=self.session_factory,
            documents=DocumentRepository,
            materials=UserMaterialRepository,
            parts=DocumentPartRepository,
            storage=self.object_storage,
            users=UserRepository,
        )

    @cached_property
    def generation_service(self) -> GenerationService:
        return GenerationService(
            session_factory=self.session_factory,
            documents=DocumentRepository,
            materials=UserMaterialRepository,
            parts=DocumentPartRepository,
            users=UserRepository,
            planner=DocumentPartPlanner(
                get_token_counter(),
                SplitLimits(self.ingest_settings.split_target_tokens, self.ingest_settings.split_max_tokens),
            ),
            storage=self.object_storage,
            ledger=self.quota_ledger,
            dispatcher=self.task_dispatcher,
            settings=self.processing_settings,
            notification_claims=self.notification_claims,
            progress_notifier=self.progress_notifier,
        )

    @cached_property
    def part_query_service(self) -> PartQueryService:
        return PartQueryService(
            session_factory=self.session_factory,
            parts=DocumentPartRepository,
            materials=UserMaterialRepository,
            images=ImageRepository,
            widgets=WidgetRepository,
            storage=self.object_storage,
        )

    @cached_property
    def quiz_check_service(self) -> QuizCheckService:
        return QuizCheckService(
            session_factory=self.session_factory,
            parts=DocumentPartRepository,
            materials=UserMaterialRepository,
            attempts=QuizAttemptRepository,
        )

    @cached_property
    def report_service(self) -> ReportService:
        return ReportService(
            session_factory=self.session_factory,
            reports=ReportRepository,
            usages=WidgetUsageRepository,
            widgets=WidgetRepository,
            decision_log=DecisionLog(metrics=self.metrics_collector),
            settings=self.reports_settings,
        )

    # -- infrastructure -----------------------------------------------------

    @cached_property
    def llm_settings(self) -> LLMSettings:
        return get_llm_settings()

    @cached_property
    def cheap_llm_overrides(self) -> CheapLLMSettings:
        return get_cheap_llm_settings()

    @cached_property
    def embeddings_settings(self) -> EmbeddingsSettings:
        return get_embeddings_settings()

    @cached_property
    def solver_settings(self) -> SolverSettings:
        return get_solver_settings()

    @cached_property
    def embeddings_redis(self) -> aioredis.Redis:
        """Dedicated cache database: flushing it must not touch Celery."""
        client: aioredis.Redis = aioredis.Redis.from_url(self.embeddings_settings.cache_redis_url)
        return client

    @cached_property
    def embedding_service(self) -> EmbeddingServiceInterface:
        settings = self.embeddings_settings
        return InstrumentedEmbeddingService(
            service=EmbeddingService(
                embedder=get_embedder(settings),
                redis=self.embeddings_redis,
                metrics=self.metrics_collector,
                batch_size=settings.batch_size,
                ttl_seconds=settings.cache_ttl_seconds,
            ),
            metrics=self.metrics_collector,
        )

    @cached_property
    def widget_search(self) -> WidgetSearch:
        """Widget search by intent."""
        return WidgetSearch(
            session_factory=self.session_factory,
            embeddings=self.embedding_service,
            settings=self.solver_settings,
            metrics=self.metrics_collector,
        )

    @cached_property
    def metrics_collector(self) -> MetricsCollector:
        return PrometheusMetricsCollector()

    @cached_property
    def main_llm(self) -> LLMClient:
        return InstrumentedLLMClient(
            client=create_llm_client(self.llm_settings),
            logger=getLogger("grasp.llm"),
            metrics=self.metrics_collector,
        )

    @cached_property
    def cheap_llm(self) -> LLMClient:
        return InstrumentedLLMClient(
            client=create_llm_client(self.cheap_llm_overrides.resolve(self.llm_settings)),
            logger=getLogger("grasp.llm.cheap"),
            metrics=self.metrics_collector,
        )

    @cached_property
    def object_storage(self) -> ObjectStorageClient:
        """S3 client over MinIO; boto3 stays hidden inside src/app/storage/.

        Three boto3 clients: the working one on the internal
        address, the signer on the public one, and a fail-fast client
        for the readiness probe whose retries cannot outlive the 5 s
        readiness budget.
        """
        settings = get_storage_settings()
        return S3ObjectStorageClient(
            settings=settings,
            client=build_s3_client(settings, endpoint_url=settings.endpoint_url),
            presign_client=build_s3_client(settings, endpoint_url=settings.public_endpoint_url),
            ping_client=build_ping_client(settings),
        )

    @cached_property
    def redis_client(self) -> aioredis.Redis:
        # Async Redis client for readiness probes.
        redis_client: aioredis.Redis = aioredis.Redis.from_url(get_celery_settings().broker_url)
        return redis_client

    @cached_property
    def progress_redis(self) -> aioredis.Redis:
        client: aioredis.Redis = aioredis.Redis.from_url(
            str(get_progress_settings().url), socket_timeout=get_progress_settings().socket_timeout
        )
        return client

    @cached_property
    def progress_reader(self) -> ProgressReader:
        return ProgressReader(self.progress_redis)

    @cached_property
    def notification_claims(self) -> RedisNotificationClaims:
        return RedisNotificationClaims(self.progress_redis)

    @cached_property
    def progress_notifier(self) -> RedisProgressNotifier:
        return RedisProgressNotifier(self.progress_redis, get_progress_settings())

    @cached_property
    def notification_service(self) -> NotificationService:
        return NotificationService(
            session_factory=self.session_factory,
            users=UserRepository,
            documents=DocumentRepository,
            parts=DocumentPartRepository,
            claims=self.notification_claims,
            sender=EmailSender(get_smtp_settings()),
            app_settings=get_app_settings(),
            smtp_settings=get_smtp_settings(),
        )

    @cached_property
    def task_dispatcher(self) -> CeleryTaskDispatcher:
        """Celery-backed queue entry point; tests replace it with a fake.

        Task names are addressed through ``send_task``, so the API stays
        decoupled from the worker's task registrations (story 1.5).
        """
        return CeleryTaskDispatcher(get_celery_settings())

    @cached_property
    def _db_engine(self) -> AsyncEngine:
        settings = get_app_settings()
        return build_engine(
            str(settings.db_url),
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            null_pool=settings.db_use_null_pool,
        )

    @cached_property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return build_session_factory(self._db_engine)

    async def close(self) -> None:
        closed_dependency_ids: set[int] = set()
        for dependency in tuple(self.__dict__.values()):
            dependency_id = id(dependency)
            if dependency_id in closed_dependency_ids:
                continue
            close = getattr(dependency, "close", None)
            if callable(close):
                result = close()
                if inspect.isawaitable(result):
                    await result
            closed_dependency_ids.add(dependency_id)

        if "_db_engine" in self.__dict__:
            await self._db_engine.dispose()
