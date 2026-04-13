"""
Shared ThreadPoolExecutor for CPU-bound ML jobs (transcription + diarization).
Isolated in its own module to avoid circular imports.

max_workers=2: at most 2 audio jobs run simultaneously — prevents OOM
and CPU saturation. Jobs beyond that are queued, not rejected.
"""
from concurrent.futures import ThreadPoolExecutor

ml_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ml_worker")
