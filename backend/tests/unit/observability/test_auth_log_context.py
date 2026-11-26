import logging
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.app.api.v1.dependencies.auth import get_auth_service, get_auth_settings, get_current_user
from src.app.core.log_context import LogContextFilter, get_log_context

pytestmark = pytest.mark.unit


def test_user_context_applies_to_authenticated_endpoint_and_is_reset(caplog: pytest.LogCaptureFixture) -> None:
    user_id = uuid4()

    class Service:
        async def get_current_user(self, token: str) -> SimpleNamespace:
            assert token == "session"
            return SimpleNamespace(id=user_id)

    logger = logging.getLogger("grasp.test-auth")
    context_filter = LogContextFilter()
    logger.addFilter(context_filter)
    app = FastAPI()
    app.dependency_overrides[get_auth_service] = lambda: Service()
    app.dependency_overrides[get_auth_settings] = lambda: SimpleNamespace(session_cookie_name="session")

    @app.get("/protected")
    async def protected(user: object = Depends(get_current_user)) -> dict[str, str]:
        logger.info("authenticated")
        return {"user_id": get_log_context()["user_id"]}

    try:
        with caplog.at_level(logging.INFO, logger="grasp.test-auth"):
            response = TestClient(app).get("/protected", cookies={"session": "session"})
        assert response.json() == {"user_id": str(user_id)}
        record = next(record for record in caplog.records if record.name == "grasp.test-auth")
        assert record.__dict__["user_id"] == str(user_id)
        assert get_log_context() == {}
    finally:
        logger.removeFilter(context_filter)
