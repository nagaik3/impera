#!/usr/bin/env python3
"""
Health Check Server para Rastreador Esteira
Expõe endpoints /health e /metrics para monitoramento externo.

Endpoints:
  GET /health              → JSON com status (sem auth)
  GET /health/detailed     → JSON detalhado (requer X-Health-Key)
  GET /metrics             → Prometheus format (requer X-Health-Key)
  GET /metrics/simplified  → JSON simples (requer X-Health-Key)

Usage:
  python3 rastreador_health_server.py              # Start server
  python3 rastreador_health_server.py --port 8000 # Custom port

Environment:
  HEALTH_CHECK_TOKEN       # Auth token for detailed endpoints
  HEALTH_CHECK_PORT        # Server port (default 5001)
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

try:
    from flask import Flask, jsonify, request
except ImportError:
    print("❌ Flask not installed. Install: pip3 install flask")
    sys.exit(1)

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from rastreador_resilience import health_check_http

# === CONFIG ===
PORT = int(os.environ.get("HEALTH_CHECK_PORT", 5001))
HOST = "127.0.0.1"
AUTH_TOKEN = os.environ.get("HEALTH_CHECK_TOKEN", "")
ENABLE_METRICS = os.environ.get("HEALTH_CHECK_METRICS", "false").lower() == "true"

app = Flask(__name__)

# === MIDDLEWARE: Auth Check ===
def require_auth(f):
    """Decorator para verificar X-Health-Key header."""
    def decorated(*args, **kwargs):
        if not AUTH_TOKEN:
            # Token not set = endpoint disabled
            return jsonify({"error": "Endpoint requires HEALTH_CHECK_TOKEN"}), 403

        provided_token = request.headers.get("X-Health-Key", "")
        if provided_token != AUTH_TOKEN:
            return jsonify({"error": "Invalid X-Health-Key"}), 401

        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated

# === ENDPOINTS ===

@app.route("/health", methods=["GET"])
def health_public():
    """
    Health check — público, sem auth.
    Retorna apenas status operacional (OK/DEGRADED/DOWN).
    """
    try:
        health = health_check_http()
        status_code = 200 if health["status"] == "operational" else 503

        return jsonify({
            "status": health["status"],
            "timestamp": health["timestamp"],
        }), status_code
    except Exception as e:
        return jsonify({
            "status": "down",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }), 500

@app.route("/health/detailed", methods=["GET"])
@require_auth
def health_detailed():
    """
    Health check detalhado — requer X-Health-Key.
    Retorna status completo com heartbeat, circuit breaker, DLQ.
    """
    try:
        health = health_check_http()
        status_code = 200 if health["status"] == "operational" else 503
        return jsonify(health), status_code
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }), 500

@app.route("/metrics", methods=["GET"])
@require_auth
def metrics_prometheus():
    """
    Prometheus metrics endpoint — requer X-Health-Key.
    Retorna métricas em formato Prometheus.
    """
    if not ENABLE_METRICS:
        return jsonify({"error": "Metrics disabled. Set HEALTH_CHECK_METRICS=true"}), 403

    try:
        health = health_check_http()

        # Converter para Prometheus format
        lines = []
        lines.append("# HELP rastreador_status Rastreador health status (1=operational, 0=degraded)")
        lines.append("# TYPE rastreador_status gauge")
        status_value = 1 if health["status"] == "operational" else 0
        lines.append(f"rastreador_status {status_value}")

        lines.append("# HELP rastreador_dlq_pending Items pending in Dead Letter Queue")
        lines.append("# TYPE rastreador_dlq_pending gauge")
        lines.append(f"rastreador_dlq_pending {health.get('dlq_pending', 0)}")

        lines.append("# HELP rastreador_circuit_breaker Circuit breaker status (0=ok, 1=tripped)")
        lines.append("# TYPE rastreador_circuit_breaker gauge")
        cb_value = 1 if "TRIPPED" in health.get("circuit_breaker", "") else 0
        lines.append(f"rastreador_circuit_breaker {cb_value}")

        return "\n".join(lines) + "\n", 200, {"Content-Type": "text/plain; charset=utf-8"}
    except Exception as e:
        return f"# ERROR: {e}\n", 500, {"Content-Type": "text/plain"}

@app.route("/metrics/simplified", methods=["GET"])
@require_auth
def metrics_json():
    """
    Métricas em JSON simples — requer X-Health-Key.
    """
    try:
        health = health_check_http()
        return jsonify({
            "status": health["status"],
            "dlq_pending": health.get("dlq_pending", 0),
            "circuit_breaker_tripped": "TRIPPED" in health.get("circuit_breaker", ""),
            "heartbeat": health.get("heartbeat", "unknown"),
            "timestamp": health["timestamp"],
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ping", methods=["GET"])
def ping():
    """
    Simple ping — sem auth, sem lógica.
    Apenas confirma que o server está rodando.
    """
    return jsonify({"ping": "pong"}), 200

# === ERROR HANDLERS ===
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({"error": "Internal server error"}), 500

# === MAIN ===
if __name__ == "__main__":
    # Parse args
    custom_port = None
    for arg in sys.argv[1:]:
        if arg.startswith("--port"):
            try:
                custom_port = int(arg.split("=")[1])
            except:
                pass

    final_port = custom_port or PORT

    print(f"🏥 Rastreador Health Server")
    print(f"   Host: {HOST}:{final_port}")
    print(f"   Auth: {'Enabled (X-Health-Key)' if AUTH_TOKEN else 'DISABLED (set HEALTH_CHECK_TOKEN)'}")
    print(f"   Metrics: {'Enabled' if ENABLE_METRICS else 'Disabled'}")
    print(f"")
    print(f"   Public endpoints:")
    print(f"      GET /ping              → Simple connectivity check")
    print(f"      GET /health            → Status only (OK/DEGRADED)")
    print(f"")
    print(f"   Protected endpoints (require X-Health-Key):")
    print(f"      GET /health/detailed   → Full status with details")
    print(f"      GET /metrics           → Prometheus format (if enabled)")
    print(f"      GET /metrics/simplified→ JSON metrics")
    print(f"")
    print(f"Starting server...")

    try:
        app.run(host=HOST, port=final_port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("\n✅ Server stopped.")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
