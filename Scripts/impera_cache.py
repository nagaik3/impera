"""
Cache compartilhado para APIs IMPERA — ClickUp + RedTrack
Evita chamadas duplicadas entre scripts que rodam próximos no crontab.

Uso:
    from impera_cache import cached_cu_tasks, cached_rt_adgroups, cached_rt_ads, rt_fetch_single

Cache de arquivo com TTL configurável. Múltiplos scripts lendo LIST_TRAFEGO
no mesmo horário usam o mesmo cache.
"""

import json
import os
import time
import urllib.request
import fcntl
from datetime import datetime, timedelta

CACHE_DIR = os.path.expanduser("~/Scripts/data/cache")
DEFAULT_TTL = 3600  # 1 hora
RT_MIN_INTERVAL = 1.5  # segundos mínimos entre chamadas RT

CLICKUP_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")


def _ensure_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def rt_rate_limit():
    """
    Rate limiter global para RedTrack API.
    Garante mínimo de RT_MIN_INTERVAL segundos entre chamadas,
    mesmo entre processos diferentes (usa fcntl file lock).
    """
    _ensure_dir()
    lock_path = os.path.join(CACHE_DIR, "rt_rate_limit.lock")
    ts_path = os.path.join(CACHE_DIR, "rt_last_call.txt")
    with open(lock_path, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            now = time.time()
            # Lê último timestamp
            try:
                with open(ts_path, "r") as tf:
                    last = float(tf.read().strip())
            except (FileNotFoundError, ValueError):
                last = 0.0
            # Espera se necessário
            elapsed = now - last
            if elapsed < RT_MIN_INTERVAL:
                time.sleep(RT_MIN_INTERVAL - elapsed)
            # Grava novo timestamp
            with open(ts_path, "w") as tf:
                tf.write(str(time.time()))
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _cache_path(key):
    return os.path.join(CACHE_DIR, f"{key}.json")


def _cleanup_stale_tmp():
    """Remove arquivos .tmp com mais de 5 minutos (processos mortos)."""
    try:
        cutoff = time.time() - 300
        for f in os.listdir(CACHE_DIR):
            if ".tmp." in f:
                fpath = os.path.join(CACHE_DIR, f)
                try:
                    if os.path.getmtime(fpath) < cutoff:
                        os.unlink(fpath)
                except OSError:
                    pass
    except OSError:
        pass


def _read_cache(key, ttl=DEFAULT_TTL):
    """Lê cache se existir e não estiver expirado."""
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        age = time.time() - os.path.getmtime(path)
        if age > ttl:
            return None
        with open(path, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            data = json.load(f)
            fcntl.flock(f, fcntl.LOCK_UN)
            return data
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(key, data):
    """Escreve no cache com lock exclusivo. Seguro para múltiplos processos."""
    _ensure_dir()
    _cleanup_stale_tmp()
    path = _cache_path(key)
    tmp = path + f".tmp.{os.getpid()}"
    try:
        with open(tmp, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
            fcntl.flock(f, fcntl.LOCK_UN)
        os.replace(tmp, path)
    except FileNotFoundError:
        # Retry once — another process may have interfered
        try:
            with open(tmp, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
                fcntl.flock(f, fcntl.LOCK_UN)
            os.replace(tmp, path)
        except OSError:
            pass  # Best-effort — next read will trigger a fresh fetch
    except OSError:
        pass  # Best-effort
    finally:
        # Clean up our tmp if it still exists (e.g., replace failed)
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


# ============================================================
# ClickUp
# ============================================================

def _cu_api_get(endpoint):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url, headers={"Authorization": CLICKUP_TOKEN})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _fetch_cu_tasks_raw(list_id, include_closed=False):
    """Busca todas as tasks de uma lista (paginado)."""
    all_tasks = []
    page = 0
    closed = "true" if include_closed else "false"
    while True:
        data = _cu_api_get(f"/list/{list_id}/task?include_closed={closed}&subtasks=true&page={page}")
        tasks = data.get("tasks", [])
        if not tasks:
            break
        all_tasks.extend(tasks)
        page += 1
    return all_tasks


def cached_cu_tasks(list_id, include_closed=False, ttl=DEFAULT_TTL, force=False):
    """
    Retorna tasks do ClickUp com cache de arquivo.
    Múltiplos scripts chamando esta função dentro do TTL compartilham o resultado.
    """
    key = f"cu_tasks_{list_id}_{'closed' if include_closed else 'open'}"
    if not force:
        cached = _read_cache(key, ttl)
        if cached is not None:
            return cached
    tasks = _fetch_cu_tasks_raw(list_id, include_closed)
    _write_cache(key, tasks)
    return tasks


# ============================================================
# RedTrack — fetch único (sem cascade N+1)
# ============================================================

def rt_fetch_single(params):
    """Chamada única ao RedTrack (sem cache). Rate-limited globalmente."""
    rt_rate_limit()
    url = "https://api.redtrack.io/report?" + "&".join(f"{k}={v}" for k, v in params.items())
    with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as resp:
        return json.loads(resp.read())


def cached_rt_adgroups(date_from, date_to, ttl=DEFAULT_TTL, force=False):
    """
    Busca adgroups com contexto de campanha.
    Usa group=campaign,rt_adgroup (multi-group: 1 chamada, retorna campaign + campaign_id + rt_adgroup).
    RT tem hard limit de 1000 rows — se exceder, faz fallback para batch por campanha.

    Retorna dict com:
      - "campaigns": lista de campanhas com cost agregado
      - "adgroups": lista de dicts, cada um com campaign, campaign_id, rt_adgroup, cost, etc.
    """
    key = f"rt_adgroups_{date_from}_{date_to}"
    if not force:
        cached = _read_cache(key, ttl)
        if cached is not None:
            return cached

    # Tentativa 1: multi-group (1 call)
    all_ags = rt_fetch_single({
        "api_key": REDTRACK_KEY, "group": "campaign,rt_adgroup",
        "date_from": date_from, "date_to": date_to, "per": "10000",
    })

    # Se atingiu 1000 rows, pode estar truncado → fallback batch
    if len(all_ags) >= 1000:
        all_ags = _fetch_rt_batch("rt_adgroup", date_from, date_to)

    campaigns = _extract_campaigns(all_ags)
    result = {"campaigns": campaigns, "adgroups": all_ags}
    _write_cache(key, result)
    return result


def cached_rt_ads(date_from, date_to, ttl=DEFAULT_TTL, force=False):
    """
    Busca ads com contexto de campanha.
    Usa group=campaign,rt_ad (multi-group).
    Fallback para batch se exceder 1000 rows.
    """
    key = f"rt_ads_{date_from}_{date_to}"
    if not force:
        cached = _read_cache(key, ttl)
        if cached is not None:
            return cached

    all_ads = rt_fetch_single({
        "api_key": REDTRACK_KEY, "group": "campaign,rt_ad",
        "date_from": date_from, "date_to": date_to, "per": "10000",
    })

    if len(all_ads) >= 1000:
        all_ads = _fetch_rt_batch("rt_ad", date_from, date_to)

    campaigns = _extract_campaigns(all_ads)
    result = {"campaigns": campaigns, "ads": all_ads}
    _write_cache(key, result)
    return result


def _extract_campaigns(rows):
    """Extrai lista de campanhas únicas a partir de rows multi-group."""
    camp_agg = {}
    for r in rows:
        cid = r.get("campaign_id", "")
        if not cid:
            continue
        if cid not in camp_agg:
            camp_agg[cid] = {"campaign_id": cid, "campaign": r.get("campaign", ""), "cost": 0}
        camp_agg[cid]["cost"] += float(r.get("cost", 0))
    return list(camp_agg.values())


def _fetch_rt_batch(sub_group, date_from, date_to):
    """
    Fallback quando multi-group excede 1000 rows.
    Busca campanhas ativas e faz batch por campanha com retry.
    """
    import time as _t
    campaigns = rt_fetch_single({
        "api_key": REDTRACK_KEY, "group": "campaign",
        "date_from": date_from, "date_to": date_to, "per": "500",
    })
    active = [c for c in campaigns if float(c.get("cost", 0)) > 0]
    all_rows = []
    for camp in active:
        cid = camp["campaign_id"]
        cname = camp.get("campaign", "")
        for attempt in range(3):
            try:
                rows = rt_fetch_single({
                    "api_key": REDTRACK_KEY, "group": sub_group,
                    "campaign_id": cid, "date_from": date_from, "date_to": date_to, "per": "1000",
                })
                for r in rows:
                    r["campaign_id"] = cid
                    r["campaign"] = cname
                all_rows.extend(rows)
                break
            except Exception as e:
                if attempt < 2:
                    _t.sleep(2 ** (attempt + 1))  # 2s, 4s backoff
                else:
                    print(f"  [WARN] RT batch falhou 3x para {cname[:40]}: {e}")
        # rate limit já garantido por rt_rate_limit() dentro de rt_fetch_single()
    return all_rows


def clear_cache(pattern=None):
    """Limpa cache. Se pattern fornecido, limpa apenas keys que contêm o pattern."""
    _ensure_dir()
    for f in os.listdir(CACHE_DIR):
        if f.endswith(".json"):
            if pattern is None or pattern in f:
                os.remove(os.path.join(CACHE_DIR, f))
