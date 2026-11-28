"""ConfigAssembler: builds and fixes widget configurations (story 2.4.2, 2.4.3)."""

import json
import logging

from jsonschema import Draft202012Validator

from src.app.contracts.solver.main_pass import MainPassDirective
from src.app.contracts.solver.valid_config import ValidConfig
from src.app.contracts.solver.widget_candidate import WidgetCandidate
from src.app.interfaces.llm.llm_client import LLMClient
from src.app.services.solver.library.primitive_catalog import PrimitiveCatalog
from src.app.services.solver.resolver.llm_outputs import ConfigDraft
from src.app.services.solver.resolver.prompts import (
    CONFIG_BUILD_SYSTEM_PROMPT,
    CONFIG_FIX_SYSTEM_PROMPT,
    render_config_build_prompt,
    render_config_fix_prompt,
)

logger = logging.getLogger(__name__)


class ConfigAssembler:
    """Builds widget configurations from primitives using the main LLM."""

    def __init__(
        self,
        main_llm: LLMClient,
        catalog: PrimitiveCatalog,
    ) -> None:
        self._llm = main_llm
        self._catalog = catalog

    async def build(self, request: MainPassDirective) -> ValidConfig | None:
        """Build a configuration from the primitive catalog."""
        # Prepare catalog data
        primitive_schemas = {}
        primitive_descriptions = {}
        primitive_modes = {}

        for pid in self._catalog.ids:
            record = await self._get_primitive_record(pid)
            if record:
                primitive_schemas[pid] = record.params_schema
                primitive_descriptions[pid] = record.description
                primitive_modes[pid] = record.modes

        if not primitive_schemas:
            return None

        prompt = render_config_build_prompt(
            request,
            primitive_schemas,
            primitive_descriptions,
            primitive_modes,
            request.params_hint,
        )

        try:
            draft = await self._llm.call_structured(
                system_prompt=CONFIG_BUILD_SYSTEM_PROMPT,
                user_prompt=prompt,
                response_model=ConfigDraft,
                purpose="config_build",
            )
        except Exception as exc:
            logger.warning("ConfigAssembler.build call failed: %s", exc)
            raise

        if draft.primitive_id is None:
            return None

        return await self._validate_and_convert(draft, request)

    async def adapt(
        self,
        candidate: WidgetCandidate,
        request: MainPassDirective,
    ) -> ValidConfig | None:
        """Adapt an existing widget's params to the new fragment (story 2.4.2)."""
        if candidate.kind.name == "CODE":
            # For code widgets, compare shape with default params
            return ValidConfig(
                primitive_id=candidate.primitive_id or "",
                mode=candidate.mode or "",
                params=candidate.params or {},
                primitive_version=1,
            )

        # For config widgets, build new params using the candidate as example
        primitive_schemas = {candidate.primitive_id: await self._get_primitive_schema(candidate.primitive_id)}
        primitive_descriptions = {candidate.primitive_id: candidate.description}
        primitive_modes = {candidate.primitive_id: [candidate.mode] if candidate.mode else []}

        prompt = render_config_build_prompt(
            request,
            primitive_schemas,
            primitive_descriptions,
            primitive_modes,
            request.params_hint,
        )

        try:
            draft = await self._llm.call_structured(
                system_prompt=CONFIG_BUILD_SYSTEM_PROMPT,
                user_prompt=prompt,
                response_model=ConfigDraft,
                purpose="config_build",
            )
        except Exception as exc:
            logger.warning("ConfigAssembler.adapt call failed: %s", exc)
            raise

        if draft.primitive_id is None:
            return None

        return await self._validate_and_convert(draft, request)

    async def fix(
        self,
        request: MainPassDirective,
        previous: ConfigDraft,
        issues: list[str],
    ) -> ValidConfig | None:
        """Fix a configuration based on validation issues (exactly one attempt)."""
        # Re-render the same catalog context
        primitive_schemas = {}
        primitive_descriptions = {}
        primitive_modes = {}

        for pid in self._catalog.ids:
            record = await self._get_primitive_record(pid)
            if record:
                primitive_schemas[pid] = record.params_schema
                primitive_descriptions[pid] = record.description
                primitive_modes[pid] = record.modes

        context = render_config_build_prompt(
            request,
            primitive_schemas,
            primitive_descriptions,
            primitive_modes,
            request.params_hint,
        )
        fix_prompt = render_config_fix_prompt(previous, issues, context)

        try:
            draft = await self._llm.call_structured(
                system_prompt=CONFIG_FIX_SYSTEM_PROMPT,
                user_prompt=fix_prompt,
                response_model=ConfigDraft,
                purpose="config_fix",
            )
        except Exception as exc:
            logger.warning("ConfigAssembler.fix call failed: %s", exc)
            raise

        if draft.primitive_id is None:
            return None

        return await self._validate_and_convert(draft, request)

    async def _validate_and_convert(
        self,
        draft: ConfigDraft,
        request: MainPassDirective,
    ) -> ValidConfig | None:
        """Parse params_json and validate against schema."""
        if draft.primitive_id not in self._catalog:
            logger.warning("ConfigAssembler: primitive %s not in catalog", draft.primitive_id)
            return None

        record = await self._get_primitive_record(draft.primitive_id)
        if not record:
            return None

        # Validate mode
        if draft.mode and draft.mode not in record.modes:
            logger.warning("ConfigAssembler: mode %s not in primitive %s modes", draft.mode, draft.primitive_id)
            return None

        # Parse and validate params_json
        try:
            params = json.loads(draft.params_json)
        except json.JSONDecodeError as exc:
            logger.warning("ConfigAssembler: invalid JSON in params_json: %s", exc)
            return None

        # Validate against JSON Schema
        validator = Draft202012Validator(record.params_schema)
        errors = list(validator.iter_errors(params))
        if errors:
            error_msgs = [f"{'.'.join(str(p) for p in e.path)}: {e.message}" for e in errors]
            logger.warning("ConfigAssembler: schema validation failed: %s", error_msgs)
            return None

        return ValidConfig(
            primitive_id=draft.primitive_id,
            mode=draft.mode or record.modes[0] if record.modes else "",
            params=params,
            primitive_version=record.version,
        )

    async def _get_primitive_record(self, primitive_id: str):
        """Get primitive record from repository (to be injected)."""
        # This will be overridden by the container with a real implementation
        return None

    async def _get_primitive_schema(self, primitive_id: str) -> dict:
        record = await self._get_primitive_record(primitive_id)
        return record.params_schema if record else {}


__all__ = ["ConfigAssembler"]