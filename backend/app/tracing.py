import contextlib
import time
from typing import Optional
from backend.app.config import SENTRY_DSN

_sentry_initialized = False

def init_tracing():
    global _sentry_initialized
    if SENTRY_DSN and not _sentry_initialized:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=SENTRY_DSN,
                traces_sample_rate=1.0,
                send_default_pii=False,
            )
            _sentry_initialized = True
        except Exception:
            pass

@contextlib.contextmanager
def trace_span(span_name: str, model_name: Optional[str] = None, chunk_count: Optional[int] = None):
    init_tracing()
    start_time = time.time()
    if SENTRY_DSN and _sentry_initialized:
        try:
            import sentry_sdk
            with sentry_sdk.start_span(op="explain_this_thing", description=span_name) as span:
                if model_name:
                    span.set_data("model_name", model_name)
                if chunk_count is not None:
                    span.set_data("chunk_count", chunk_count)
                yield span
                duration_ms = (time.time() - start_time) * 1000
                span.set_data("duration_ms", duration_ms)
                return
        except Exception:
            pass
    
    # Fallback when Sentry is not configured or fails
    yield None
