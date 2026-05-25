"""Retry decorator for API calls — urllib + requests support."""

import time
import functools
import urllib.error

def retry_api_call(max_retries=3, backoff=2):
    """
    Decorator para retry em API calls com backoff exponencial.
    Suporta urllib.request e requests library.

    Exemplo:
        @retry_api_call(max_retries=3)
        def fetch_api():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retry_count = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Handle urllib errors
                    if isinstance(e, (urllib.error.URLError, urllib.error.HTTPError,
                                    TimeoutError, ConnectionError)):
                        pass
                    # Handle requests errors
                    elif hasattr(e, '__module__') and 'requests' in e.__module__:
                        pass
                    # Handle other network errors
                    elif any(x in str(type(e).__name__) for x in
                           ['Timeout', 'Connection', 'HTTPError', 'URLError']):
                        pass
                    else:
                        raise  # Re-raise if not a transient error

                    retry_count += 1
                    if retry_count >= max_retries:
                        print(f"  ❌ {func.__name__} falhou após {max_retries} tentativas: {e}")
                        raise
                    wait_time = backoff ** retry_count
                    print(f"  ⏳ {func.__name__} retry {retry_count}/{max_retries} — aguardando {wait_time}s...")
                    time.sleep(wait_time)
        return wrapper
    return decorator
