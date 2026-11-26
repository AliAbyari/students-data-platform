#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo
echo "  Students Data Platform"
echo "  SQL Server > Airflow + Spark > PostgreSQL > ClickHouse  |  Debezium > Kafka > Spark Streaming"
echo

is_wsl() { grep -qsi microsoft /proc/version; }
DESKTOP_EXE="/mnt/c/Program Files/Docker/Docker/Docker Desktop.exe"

if ! command -v docker >/dev/null; then
  echo "[ERROR] Docker was not found."
  if is_wsl; then
    if [[ -f "$DESKTOP_EXE" ]]; then
      echo "        Docker Desktop is installed on Windows but not shared with this distro:"
      echo "        Docker Desktop > Settings > Resources > WSL Integration > enable this distro > Apply & Restart."
    else
      echo "        Install Docker Desktop for Windows (https://www.docker.com/products/docker-desktop/)"
      echo "        and enable WSL Integration, or install Docker Engine inside WSL:"
      echo "          curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker \$USER"
    fi
  else
    echo "        Install Docker Engine: https://docs.docker.com/engine/install/"
  fi
  exit 1
fi

if grep -qs '"credsStore": *"desktop.exe"' "${DOCKER_CONFIG:-$HOME/.docker}/config.json" \
   && ! docker-credential-desktop.exe list >/dev/null 2>&1; then
  export DOCKER_CONFIG="$(mktemp -d)"
  echo '{}' > "$DOCKER_CONFIG/config.json"
  [[ -d "$HOME/.docker/cli-plugins" ]] && ln -s "$HOME/.docker/cli-plugins" "$DOCKER_CONFIG/cli-plugins"
fi

wait_for_docker() {
  local _
  for _ in $(seq 1 60); do
    docker info >/dev/null 2>&1 && return 0
    sleep 3
  done
  return 1
}

if ! docker info >/dev/null 2>&1; then
  if docker info 2>&1 | grep -qi "permission denied"; then
    echo "[ERROR] This user cannot access the Docker daemon. Run once, then open a new terminal:"
    echo "          sudo usermod -aG docker \$USER"
    exit 1
  fi
  if is_wsl && [[ -f "$DESKTOP_EXE" ]]; then
    echo "[setup] Starting Docker Desktop ..."
    (cd /mnt/c && cmd.exe /c start "" "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe" >/dev/null 2>&1) || true
  elif command -v systemctl >/dev/null && [[ -d /run/systemd/system ]]; then
    echo "[setup] Starting the Docker service (sudo may ask for your password) ..."
    sudo systemctl start docker || true
  elif command -v service >/dev/null; then
    echo "[setup] Starting the Docker service (sudo may ask for your password) ..."
    sudo service docker start || true
  fi
  wait_for_docker || { echo "[ERROR] The Docker daemon is not running. Start Docker and run this script again."; exit 1; }
fi

docker compose version >/dev/null 2>&1 || { echo "[ERROR] Docker Compose v2 is required (the 'docker compose' plugin)."; exit 1; }
if [[ "$(docker info --format '{{.OSType}}')" != "linux" ]]; then
  echo "[ERROR] Docker is running Windows containers. Switch Docker Desktop to Linux containers."
  exit 1
fi

if [[ ! -f data/Students.bak ]]; then

  if compgen -G "data/Students.bak.tar.gz.[0-9][0-9][0-9]" >/dev/null; then
    echo "[setup] Unpacking the Students database backup ..."
    cat data/Students.bak.tar.gz.[0-9][0-9][0-9] | tar -xzf - -C data
  elif [[ -f ../Students.bak ]]; then
    echo "[setup] Copying ../Students.bak to data/Students.bak"
    cp ../Students.bak data/Students.bak
  else
    echo "[ERROR] The backup parts data/Students.bak.tar.gz.* are missing. Clone the full repository again."
    exit 1
  fi
fi
chmod a+r data/Students.bak

if [[ ! -f .env ]]; then
  echo "[setup] Creating .env from .env.example"
  cp .env.example .env
  chmod 600 .env
fi
set -a; source .env; set +a

if [[ -z "${DOCKERHUB_MIRROR:-}" || "${DOCKERHUB_MIRROR}" == "auto" ]]; then
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://registry-1.docker.io/v2/ || true)
  if [[ "$code" == "401" || "$code" == "200" ]]; then
    DOCKERHUB_MIRROR=docker.io
  else
    DOCKERHUB_MIRROR=docker.arvancloud.ir
  fi
  export DOCKERHUB_MIRROR
fi
echo "[setup] Docker Hub images from: ${DOCKERHUB_MIRROR}"

mem_gb=$(( $(docker info --format '{{.MemTotal}}') / 1024 / 1024 / 1024 ))
if (( mem_gb < 7 )); then
  echo "[warning] Docker has about ${mem_gb} GB of memory; 8 GB or more is recommended."
  is_wsl && echo "          Raise it in %UserProfile%\\.wslconfig ([wsl2] memory=10GB) and run: wsl --shutdown"
fi

if [[ -z "$(docker compose ps -q 2>/dev/null)" ]]; then
  busy=()
  for port in "$PORT_PORTAL" "$PORT_AIRFLOW" "$PORT_GRAFANA" "$PORT_KAFKA_UI" "$PORT_CONNECT" \
              "$PORT_CLICKHOUSE_HTTP" "$PORT_SQLSERVER" "$PORT_POSTGRES" "${PORT_PROMETHEUS:-9091}"; do
    (exec 3<>"/dev/tcp/127.0.0.1/${port}") 2>/dev/null && busy+=("$port")
  done
  if (( ${#busy[@]} )); then
    echo "[ERROR] These ports are already in use: ${busy[*]}. Free them or change the PORT_* values in .env."
    exit 1
  fi
fi

retry() {
  local attempt
  for attempt in 1 2 3 4 5; do
    "$@" && return 0
    echo "[retry] attempt ${attempt} failed: $*"
    sleep 10
  done
  return 1
}

echo
echo "[1/4] Downloading images (first run: about 5-10 minutes, depending on the connection) ..."
retry docker compose pull --ignore-buildable || { echo "[ERROR] Images could not be downloaded. Set DOCKERHUB_MIRROR in .env."; exit 1; }

echo
echo "[2/4] Building the platform images (first run: about 5-10 minutes; later runs use the cache) ..."
retry docker compose build || { echo "[ERROR] Image build failed."; exit 1; }

echo
echo "[3/4] Starting the services ..."
docker compose up -d

echo
echo "[4/4] Waiting until every service is ready (first run: SQL Server restores the database, about 2-5 minutes) ..."
status() {
  local total=0 done=0 pending="" svc state health
  while read -r svc state health; do
    [[ -z "$svc" ]] && continue
    total=$((total + 1))
    if { [[ "$state" == running && "$health" != starting && "$health" != unhealthy ]]; } \
       || { [[ "$state" == exited && ( "$svc" == *init* || "$svc" == *register* ) ]]; }; then
      done=$((done + 1))
    else
      pending+=" $svc"
    fi
  done < <(docker compose ps -a --format '{{.Service}} {{.State}} {{.Health}}' 2>/dev/null)
  printf '  [%d:%02d] %d/%d services ready - %s\n' $(($1 / 60)) $(($1 % 60)) "$done" "$total" \
    "${pending:+starting:$pending}${pending:-waiting for the portal}"
}
for i in $(seq 1 180); do
  if curl -fs "http://localhost:${PORT_PORTAL}/health" >/dev/null 2>&1; then
    ready=1; break
  fi
  (( i % 2 == 1 )) && status $(( (i - 1) * 5 ))
  sleep 5
done
if [[ -z "${ready:-}" ]]; then
  echo "[ERROR] The portal did not become healthy in time. Inspect: docker compose logs portal mssql-init"
  exit 1
fi

echo
echo "[done] Platform is up. Opening the portal in your browser ..."
cat <<INFO

  Students Portal (Blazor PWA)  http://localhost:${PORT_PORTAL}     user: ${PORTAL_ADMIN_USER}  password: ${PORTAL_ADMIN_PASSWORD}
  Airflow                       http://localhost:${PORT_AIRFLOW}     user: ${AIRFLOW_ADMIN_USER}  password: ${AIRFLOW_ADMIN_PASSWORD}
  Grafana                       http://localhost:${PORT_GRAFANA}     user: ${GRAFANA_ADMIN_USER}  password: ${GRAFANA_ADMIN_PASSWORD}
  Kafka UI                      http://localhost:${PORT_KAFKA_UI}
  Prometheus                    http://localhost:${PORT_PROMETHEUS:-9091}
  ClickHouse HTTP               http://localhost:${PORT_CLICKHOUSE_HTTP}
  SQL Server                    localhost,${PORT_SQLSERVER}   (sa / see .env)

  The initial warehouse load runs automatically in Airflow (DAG students_batch_scd)
  and takes a few minutes; the dashboard fills in when it finishes.
INFO

if is_wsl && command -v cmd.exe >/dev/null; then
  (cd /mnt/c && cmd.exe /c start "" "http://localhost:${PORT_PORTAL}" >/dev/null 2>&1) || true
elif command -v xdg-open >/dev/null; then
  xdg-open "http://localhost:${PORT_PORTAL}" >/dev/null 2>&1 || true
elif command -v open >/dev/null; then
  open "http://localhost:${PORT_PORTAL}" >/dev/null 2>&1 || true
fi
