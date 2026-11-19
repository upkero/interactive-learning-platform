"""Progress stream dependencies."""

from typing import Annotated

from fastapi import Depends

from src.app.api.v1.dependencies.container import ContainerDep
from src.app.services.progress.progress_reader import ProgressReader


def get_progress_reader(container: ContainerDep) -> ProgressReader:
    return ProgressReader(container.progress_redis)


ProgressReaderDep = Annotated[ProgressReader, Depends(get_progress_reader)]
