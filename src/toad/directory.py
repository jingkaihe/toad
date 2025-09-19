from __future__ import annotations

import asyncio
from asyncio import to_thread
import fnmatch
from typing import Callable, Sequence

from time import time
from os import PathLike

from pathlib import Path


class ScanJob:
    """A single directory scanning job."""

    def __init__(
        self,
        name: str,
        queue: asyncio.Queue[Path],
        results: list[Path],
        exclude_dirs: Sequence[str],
        exclude_files: Sequence[str],
    ) -> None:
        self.queue = queue
        self.results = results
        self.exclude_dirs = exclude_dirs
        self.exclude_files = exclude_files
        self.name = name

    def start(self) -> None:
        self._task = asyncio.create_task(self.run())

    async def run(self) -> None:
        queue = self.queue
        results = self.results
        while True:
            try:
                scan_path = await queue.get()
            except asyncio.QueueShutDown:
                break
            paths = await to_thread(self._scan, scan_path)
            for path in paths:
                if path.is_file():
                    str_path = str(path.name)
                    for exclude in self.exclude_files:
                        if fnmatch.fnmatch(str_path, exclude):
                            break
                    else:
                        results.append(path)
                elif path.is_dir():
                    str_path = str(path.name)
                    for exclude in self.exclude_dirs:
                        if fnmatch.fnmatch(str_path, exclude):
                            break
                    else:
                        # results.append(path)
                        await queue.put(path)
            queue.task_done()

    def _scan(self, root: Path) -> list[Path]:
        try:
            return list(root.iterdir())
        except IOError:
            return []


async def scan(
    root: Path,
    max_simultaneous: int = 5,
    exclude_dirs: Sequence[str] | None = None,
    exclude_files: Sequence[str] | None = None,
) -> list[Path]:
    """Scan a directory for paths.

    Args:
        root: Root directory to scan.
        max_simultaneous: Maximum number of scan jobs.
        exclude_dirs: Wildcards to exclude directories.
        exclude_files: Wildcards to exclude paths.

    Returns:
        A list of Paths.
    """
    queue: asyncio.Queue[Path] = asyncio.Queue()
    results: list[Path] = []
    jobs = [
        ScanJob(
            f"scan-job #{index}",
            queue,
            results,
            exclude_dirs=exclude_dirs or [],
            exclude_files=exclude_files or [],
        )
        for index in range(max_simultaneous)
    ]
    try:
        await queue.put(root)
        for job in jobs:
            job.start()
        await queue.join()
    except asyncio.CancelledError:
        await queue.join()
    queue.shutdown(immediate=True)
    return results


class Scan:
    """A scan of a single directory."""

    def __init__(self, root: Path, on_complete: Callable[[Scan]]) -> None:
        self.root = root
        self._on_complete = on_complete
        self._complete_event = asyncio.Event()
        self._scan_result: list[Path] = []
        self._scan_task: asyncio.Task | None = None
        self._scan_time = time()

    @property
    def is_complete(self) -> bool:
        """Has the scan finished?"""
        return self._complete_event.is_set()

    def start(self) -> None:
        self._scan_time = time()
        self._scan_task = asyncio.create_task(self._run(), name=f"scan {self.root!s}")

    async def _run(self) -> None:
        await asyncio.to_thread(self._scan)
        self._complete_event.set()
        self._on_complete(self)

    def _scan(self) -> None:
        self._scan_result = list(self.root.iterdir())

    async def wait(self) -> list[Path]:
        """Get the result of the scan, potentially waiting for it to finish first.

        Returns:
            A list of paths in the root.
        """
        await self._complete_event.wait()
        assert self._scan_result is not None
        self._scan_task = None
        return self._scan_result


class DirectoryScanner:
    def __init__(self, root: PathLike) -> None:
        self.root = Path(root)
        self.directories: dict[Path, Scan] = {}

    async def scan(
        self, relative_directory_path: str, on_complete: Callable[[Scan]]
    ) -> Scan:
        """Get a scan.

        Scans are created on demand, or returned previously scanned.

        Args:
            relative_directory_path: A path relative to the root.
            on_complete: Callback when scan is complete, will be invoked with Scan instance.

        Returns:
            A scan instance.
        """
        scan_path = self.root / relative_directory_path
        if scan := self.directories.get(scan_path):
            if scan.is_complete:
                on_complete(scan)
        else:
            self.directories[scan_path] = scan = Scan(
                scan_path, on_complete=on_complete
            )
            scan.start()
        return scan


if __name__ == "__main__":
    # from rich import print

    from textual.fuzzy import Matcher

    import contextlib
    from time import perf_counter
    from typing import Generator

    @contextlib.contextmanager
    def timer(subject: str = "time") -> Generator[None, None, None]:
        """print the elapsed time. (only used in debugging)"""
        start = perf_counter()
        yield
        elapsed = perf_counter() - start
        elapsed_ms = elapsed * 1000
        print(f"{subject} elapsed {elapsed_ms:.4f}ms")

    async def run_scan():
        paths = await scan(
            Path("./"),
            # exclude_dirs=[".*", "__pycache__"],
        )
        str_paths = [str(path) for path in paths]
        matcher = Matcher("psputils")
        results = []

        with timer("fuzzy"):
            for path in str_paths:
                score = matcher.match(path)
                if score > 0:
                    print(path)
                results.append((score, path))

        # print(results)

    asyncio.run(run_scan())
