import http.client
import json
import os
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote

SOCKET = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")
PROJECT = os.environ.get("COMPOSE_PROJECT", "students-platform")
PORT = int(os.environ.get("EXPORTER_PORT", "9417"))
INTERVAL = float(os.environ.get("REFRESH_SECONDS", "10"))


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self):
        super().__init__("localhost", timeout=20)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(20)
        self.sock.connect(SOCKET)


def docker_get(path):
    conn = _UnixConnection()
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        if resp.status != 200:
            raise RuntimeError(f"{path}: HTTP {resp.status}")
        return json.loads(body)
    finally:
        conn.close()


def _escape(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _parse_time(value):
    if not value or value.startswith("0001-"):
        return 0.0
    head, _, frac = value.rstrip("Z").partition(".")
    seconds = datetime.fromisoformat(head + "+00:00").timestamp()
    return seconds + (float("0." + frac[:6]) if frac else 0.0)


class Collector:
    def __init__(self):
        self.text = "# no data collected yet\n"
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=8)

    def _container(self, summary):
        cid = summary["Id"]
        detail = docker_get(f"/containers/{cid}/json")
        stats = None
        if detail["State"].get("Running"):
            try:
                stats = docker_get(f"/containers/{cid}/stats?stream=false&one-shot=true")
            except Exception:
                stats = None
        return summary, detail, stats

    def collect(self):
        started = time.time()
        flt = quote(json.dumps({"label": [f"com.docker.compose.project={PROJECT}"]}))
        summaries = docker_get(f"/containers/json?all=1&filters={flt}")
        info = docker_get("/info")
        results = list(self.pool.map(self._container, summaries))

        series = {}

        def add(name, labels, value, kind="gauge", help_text=""):
            entry = series.setdefault(name, {"kind": kind, "help": help_text, "rows": []})
            rendered = ",".join(f'{k}="{_escape(v)}"' for k, v in labels.items())
            entry["rows"].append(f"{name}{{{rendered}}} {value}" if rendered else f"{name} {value}")

        for summary, detail, stats in results:
            labels_src = summary.get("Labels") or {}
            service = labels_src.get("com.docker.compose.service", summary["Names"][0].lstrip("/"))
            name = summary["Names"][0].lstrip("/")
            state = detail["State"]
            health = (state.get("Health") or {}).get("Status", "none")
            base = {"service": service, "name": name}

            add("docker_container_info", {**base, "image": summary.get("Image", ""), "state": state.get("Status", ""),
                                          "health": health}, 1, help_text="Container metadata; value is always 1.")
            add("docker_container_running", base, int(bool(state.get("Running"))), help_text="1 when the container is running.")
            if health != "none":
                add("docker_container_healthy", base, int(health == "healthy"),
                    help_text="1 when the Docker healthcheck reports healthy.")
            add("docker_container_restart_count", base, detail.get("RestartCount", 0), help_text="Restarts done by Docker.")
            add("docker_container_started_at_seconds", base, _parse_time(state.get("StartedAt")),
                help_text="Last start time, unix seconds.")
            add("docker_container_exit_code", base, state.get("ExitCode", 0), help_text="Exit code of the last run.")
            add("docker_container_oom_killed", base, int(bool(state.get("OOMKilled"))), help_text="1 if killed by the OOM killer.")

            if not stats:
                continue
            cpu = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
            add("docker_container_cpu_seconds_total", base, cpu / 1e9, "counter", "CPU time consumed, seconds.")
            mem = stats.get("memory_stats", {})
            inactive = (mem.get("stats") or {}).get("inactive_file", 0)
            add("docker_container_memory_working_set_bytes", base, max(mem.get("usage", 0) - inactive, 0),
                help_text="Memory usage without inactive page cache (as docker stats).")
            add("docker_container_memory_limit_bytes", base, mem.get("limit", 0), help_text="Memory limit of the container.")
            rx = sum(n.get("rx_bytes", 0) for n in (stats.get("networks") or {}).values())
            tx = sum(n.get("tx_bytes", 0) for n in (stats.get("networks") or {}).values())
            add("docker_container_network_receive_bytes_total", base, rx, "counter", "Bytes received.")
            add("docker_container_network_transmit_bytes_total", base, tx, "counter", "Bytes sent.")
            io = (stats.get("blkio_stats") or {}).get("io_service_bytes_recursive") or []
            add("docker_container_block_read_bytes_total", base,
                sum(e.get("value", 0) for e in io if e.get("op", "").lower() == "read"), "counter", "Bytes read from disk.")
            add("docker_container_block_write_bytes_total", base,
                sum(e.get("value", 0) for e in io if e.get("op", "").lower() == "write"), "counter", "Bytes written to disk.")
            add("docker_container_pids", base, (stats.get("pids_stats") or {}).get("current", 0), help_text="Processes/threads.")

        add("docker_host_cpus", {}, info.get("NCPU", 0), help_text="CPUs available to Docker.")
        add("docker_host_memory_bytes", {}, info.get("MemTotal", 0), help_text="Memory available to Docker.")
        add("docker_exporter_up", {}, 1, help_text="1 when the last collection succeeded.")
        add("docker_exporter_collect_duration_seconds", {}, round(time.time() - started, 3),
            help_text="Time the last collection took.")

        lines = []
        for name, entry in series.items():
            lines.append(f"# HELP {name} {entry['help']}")
            lines.append(f"# TYPE {name} {entry['kind']}")
            lines.extend(entry["rows"])
        with self.lock:
            self.text = "\n".join(lines) + "\n"

    def loop(self):
        while True:
            try:
                self.collect()
            except Exception as exc:
                with self.lock:
                    self.text = f"# collection failed: {_escape(exc)}\ndocker_exporter_up 0\n"
            time.sleep(INTERVAL)


COLLECTOR = Collector()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/metrics", "/"):
            self.send_error(404)
            return
        with COLLECTOR.lock:
            body = COLLECTOR.text.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    threading.Thread(target=COLLECTOR.loop, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
