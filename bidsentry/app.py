"""Application dependency wiring."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from bidsentry.config import Settings
from bidsentry.controllers.audit_controller import AuditController, PortfolioController
from bidsentry.core.auth import audit_seal_key
from bidsentry.controllers.dispatch_controller import DispatchController
from bidsentry.evaluators.engine import EvaluationEngine
from bidsentry.lib.audit_log import AuditLog
from bidsentry.services.audit_service import AuditService
from bidsentry.services.boq_export_service import BoQExportService
from bidsentry.services.comprehensive_audit_service import ComprehensiveAuditService
from bidsentry.services.dispatch_service import DispatchService
from bidsentry.services.document_extraction_service import DocumentExtractionService
from bidsentry.services.langflow_service import LangflowService
from bidsentry.services.portfolio_service import PortfolioService
from bidsentry.services.settings_service import SettingsService
from bidsentry.services.watsonx_service import WatsonxService
from bidsentry.services.workbook_export_service import WorkbookExportService


@dataclass
class Application:
    settings: Settings
    audit: AuditController
    portfolio: PortfolioController
    dispatch: DispatchController
    documents: DocumentExtractionService
    langflow: LangflowService
    watsonx: WatsonxService
    audit_log: AuditLog
    comprehensive_audit: ComprehensiveAuditService
    settings_service: SettingsService
    workbook_export: WorkbookExportService
    evaluation_engine: EvaluationEngine
    boq_export: BoQExportService

    def apply_settings(self, settings: Settings) -> None:
        """Propagate saved settings to every service that holds a reference."""
        self.settings = settings
        self.langflow.settings = settings
        self.watsonx.settings = settings
        self.evaluation_engine.settings = settings
        self.dispatch.service.settings = settings


def create_application(settings: Settings | None = None) -> Application:
    config = settings or Settings.from_environment()
    audit_log = AuditLog(config.audit_log_path, seal_key=audit_seal_key(config))
    try:
        audit_log.purge_older_than(config.audit_retention_days)
    except Exception:
        pass
    valid, records, message = audit_log.verify_chain()
    if not valid:
        logging.getLogger("bidsentry.audit_log").warning("Integritas audit log gagal (%s catatan): %s", records, message)
    langflow = LangflowService(config)
    watsonx = WatsonxService(config)
    evaluation_engine = EvaluationEngine(config, langflow)
    return Application(
        settings=config,
        audit=AuditController(AuditService(evaluation_engine), langflow, audit_log, watsonx=watsonx),
        portfolio=PortfolioController(PortfolioService(audit_log)),
        dispatch=DispatchController(DispatchService(config), audit_log),
        documents=DocumentExtractionService(),
        langflow=langflow,
        watsonx=watsonx,
        audit_log=audit_log,
        comprehensive_audit=ComprehensiveAuditService(config, langflow),
        settings_service=SettingsService(config.workspace_root / ".env"),
        workbook_export=WorkbookExportService(),
        evaluation_engine=evaluation_engine,
        boq_export=BoQExportService(),
    )
