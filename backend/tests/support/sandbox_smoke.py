"""Run from the worker image on sandbox_net; no database or paid API needed."""

import asyncio
import base64
from struct import unpack

import httpx

from src.app.contracts.sandbox.run import SandboxRunRequest
from src.app.sandbox.http_sandbox_client import HttpSandboxClient


async def main() -> None:
    async with httpx.AsyncClient(base_url="http://sandbox:3001", timeout=35) as http:
        assert (await http.get("/health")).json() == {"status": "ok"}
        client = HttpSandboxClient(client=http)
        result = await client.run(
            SandboxRunRequest(
                source_tsx="export default function Widget({params}) { return <div>{params.value}</div> }",
                param_sets=({"value": "one"}, {"value": "two"}, {"value": "three"}),
            )
        )
        assert result.ok, result.console_errors
        assert not result.console_errors
        assert len(result.images) == 4
        for image in result.images:
            png = base64.b64decode(image.data_base64)
            assert png[1:4] == b"PNG"
            assert unpack(">II", png[16:24]) == (800, 500)
        print("Worker network sandbox smoke: 4 PNG screenshots, no errors")


if __name__ == "__main__":
    asyncio.run(main())
