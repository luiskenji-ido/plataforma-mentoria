/**
 * Bootstrap da EC2 (Ubuntu): gerado como texto puro, sem segredos.
 * - instala o Docker Engine pelo repositório oficial (download.docker.com) e o plugin Compose;
 * - instala a AWS CLI (snap oficial) para ler o SSM Parameter Store e autenticar no ECR pelo papel IAM;
 * - formata (só se estiver vazio) e monta os volumes EBS de dados pelo UUID, com nofail no /etc/fstab;
 * - grava /opt/app (compose, scripts, unidade systemd) e sobe a aplicação.
 * Os segredos ficam no SSM Parameter Store (SecureString) e só são lidos na instância, no deploy.
 */
import type { DeploymentConfig } from "@infra/shared";

export interface BootstrapInput {
  config: DeploymentConfig;
  region: string;
  ssmPrefix: string;
  /** Volumes já criados, na ordem de config.dataVolumes. */
  volumes: { volumeId: string; mountPath: string; deviceName: string }[];
}

export const APP_DIR = "/opt/app";
export const BOOTSTRAP_DONE_FILE = "/var/lib/app-bootstrap/done";
export const BOOTSTRAP_LOG = "/var/log/app-bootstrap.log";

/** Só deixa passar texto que já foi validado pelos schemas (nomes, caminhos, portas): defesa em profundidade. */
function safe(value: string | number, pattern = /^[A-Za-z0-9_./:@-]+$/): string {
  const text = String(value);
  if (!pattern.test(text)) {
    throw new Error(`Valor inseguro para o script de bootstrap: ${JSON.stringify(text)}`);
  }
  return text;
}

export function deviceNameFor(index: number): string {
  return `/dev/sd${String.fromCharCode("f".charCodeAt(0) + index)}`;
}

/** docker-compose.yml da aplicação (e do MySQL, quando ligado). A imagem vem de ${IMAGE} no /opt/app/.env. */
export function renderCompose(config: DeploymentConfig): string {
  const app = config.application;
  const firstMount = config.dataVolumes[0]?.mountPath;
  const port = safe(app.containerPort);
  const health = safe(app.healthPath, /^\/[A-Za-z0-9/_.-]*$/);
  const url = `http://127.0.0.1:${port}${health}`;
  const lines: string[] = [
    `name: ${safe(app.name)}`,
    "services:",
    "  app:",
    "    image: ${IMAGE:?defina IMAGE em /opt/app/.env}",
    `    restart: ${safe(app.restartPolicy)}`,
    "    env_file:",
    `      - ${APP_DIR}/app.env`,
    "    environment:",
    `      PORT: "${port}"`,
    "    ports:",
    `      - "${safe(app.hostPort)}:${port}"`,
  ];
  if (app.volumes.length) {
    lines.push("    volumes:");
    for (const v of app.volumes) {
      lines.push(`      - ${safe(v.hostPath)}:${safe(v.containerPath)}`);
    }
  }
  if (app.database.enabled) {
    lines.push("    depends_on:", "      mysql:", "        condition: service_healthy");
  }
  lines.push(
    "    healthcheck:",
    // curl, wget ou python: funciona em imagens slim (a da plataforma tem python)
    `      test: ["CMD-SHELL", "curl -fsS ${url} >/dev/null 2>&1 || wget -qO- ${url} >/dev/null 2>&1 || python3 -c \\"import urllib.request; urllib.request.urlopen('${url}', timeout=4)\\""]`,
    "      interval: 30s",
    "      timeout: 6s",
    "      retries: 3",
    "      start_period: 90s",
    "    logging:",
    "      driver: json-file",
    "      options:",
    '        max-size: "10m"',
    '        max-file: "3"',
  );
  if (app.database.enabled && firstMount) {
    lines.push(
      "  mysql:",
      `    image: ${safe(app.database.image)}`,
      "    restart: unless-stopped",
      "    env_file:",
      `      - ${APP_DIR}/db.env`,
      "    volumes:",
      `      - ${safe(firstMount)}/mysql:/var/lib/mysql`,
      "    healthcheck:",
      '      test: ["CMD-SHELL", "mysqladmin ping -h 127.0.0.1 --silent"]',
      "      interval: 10s",
      "      timeout: 5s",
      "      retries: 12",
      "      start_period: 60s",
      "    logging:",
      "      driver: json-file",
      "      options:",
      '        max-size: "10m"',
      '        max-file: "3"',
    );
  }
  return `${lines.join("\n")}\n`;
}

/** Converte a saída JSON do get-parameters-by-path em arquivo de ambiente do Compose (valores entre aspas simples). */
export const WRITE_ENV_PY = `import json, sys
dados = json.load(sys.stdin)
for p in sorted(dados.get("Parameters", []), key=lambda p: p["Name"]):
    chave = p["Name"].rsplit("/", 1)[1]
    valor = p["Value"]
    if "\\n" in valor or "'" in valor:
        sys.exit("valor inválido em " + chave)
    print(f"{chave}='{valor}'")
`;

export function renderDeployScript(region: string, ssmPrefix: string, withDatabase: boolean): string {
  const r = safe(region);
  const prefix = safe(ssmPrefix);
  return `#!/bin/bash
# Publica a imagem registrada em ${prefix}/image: lê as variáveis do SSM (SecureString), autentica no ECR pelo
# papel IAM da instância, baixa a imagem e (re)cria os contêineres. Seguro para rodar várias vezes.
set -euo pipefail
export PATH="/snap/bin:/usr/local/bin:/usr/bin:/bin"
cd ${APP_DIR}
IMAGE="$(aws ssm get-parameter --region ${r} --name ${prefix}/image --query Parameter.Value --output text)"
if [ "$IMAGE" = "none" ]; then
  echo "Nenhuma imagem publicada ainda (${prefix}/image = none)."
  exit 0
fi
umask 077
aws ssm get-parameters-by-path --region ${r} --path ${prefix}/env/ --with-decryption --recursive --output json \\
  | python3 ${APP_DIR}/write_env.py > ${APP_DIR}/app.env.tmp && mv ${APP_DIR}/app.env.tmp ${APP_DIR}/app.env
${
  withDatabase
    ? `aws ssm get-parameters-by-path --region ${r} --path ${prefix}/db/ --with-decryption --recursive --output json \\
  | python3 ${APP_DIR}/write_env.py > ${APP_DIR}/db.env.tmp && mv ${APP_DIR}/db.env.tmp ${APP_DIR}/db.env`
    : "true"
}
printf 'IMAGE=%s\\n' "$IMAGE" > ${APP_DIR}/.env
REGISTRY="\${IMAGE%%/*}"
aws ecr get-login-password --region ${r} | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null
docker compose --project-directory ${APP_DIR} -f ${APP_DIR}/docker-compose.yml pull
docker compose --project-directory ${APP_DIR} -f ${APP_DIR}/docker-compose.yml up -d --remove-orphans
docker logout "$REGISTRY" >/dev/null || true
docker image prune -f >/dev/null || true
echo "Imagem em execução: $IMAGE"
`;
}

/** Status para o painel (lido pelo SSM Run Command com um comando fixo). */
export const STATUS_SCRIPT = `#!/bin/bash
export PATH="/snap/bin:/usr/local/bin:/usr/bin:/bin"
echo "bootstrap=$( [ -f ${BOOTSTRAP_DONE_FILE} ] && echo done || echo pending )"
echo "docker=$(systemctl is-active docker 2>/dev/null || echo missing)"
echo "docker_version=$(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',')"
echo "ubuntu=$(. /etc/os-release && echo "$VERSION_ID")"
echo "image=$(cat ${APP_DIR}/.env 2>/dev/null | sed -n 's/^IMAGE=//p')"
docker ps -a --format 'container={{.Names}}|{{.State}}|{{.Status}}' 2>/dev/null || true
`;

export function renderSystemdUnit(config: DeploymentConfig): string {
  const mounts = config.dataVolumes.map((v) => safe(v.mountPath)).join(" ");
  return `[Unit]
Description=Aplicação ${safe(config.application.name)} (docker compose)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target
${mounts ? `RequiresMountsFor=${mounts}` : ""}

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${APP_DIR}
ExecStart=/bin/bash -c 'if [ -f ${APP_DIR}/.env ]; then docker compose --project-directory ${APP_DIR} -f ${APP_DIR}/docker-compose.yml up -d; fi'
ExecStop=/usr/bin/docker compose --project-directory ${APP_DIR} -f ${APP_DIR}/docker-compose.yml stop
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
`;
}

function heredoc(path: string, content: string, mode: string): string {
  const marker = "ARQUIVO_FIM_7f3a";
  if (content.includes(marker)) {
    throw new Error("conteúdo inválido");
  }
  return `cat > ${path} <<'${marker}'\n${content}${content.endsWith("\n") ? "" : "\n"}${marker}\nchmod ${mode} ${path}\n`;
}

/** Script de user data (cloud-init roda uma vez, no primeiro boot). Não contém segredos. */
export function renderUserData(input: BootstrapInput): string {
  const { config } = input;
  const withDatabase = config.application.database.enabled;
  const mountLines = input.volumes
    .map((v) => `mount_volume ${safe(v.volumeId, /^vol-[0-9a-f]+$/)} ${safe(v.mountPath)} ${safe(v.deviceName)}`)
    .join("\n");
  const appDirs = config.application.volumes.map((v) => safe(v.hostPath));
  const firstMount = config.dataVolumes[0]?.mountPath;
  if (withDatabase && firstMount) {
    appDirs.push(`${safe(firstMount)}/mysql`);
  }
  return `#!/bin/bash
# Bootstrap gerado pelo painel de infraestrutura (sem segredos). Log: ${BOOTSTRAP_LOG}
set -euo pipefail
exec > >(tee -a ${BOOTSTRAP_LOG}) 2>&1
echo "[bootstrap] início $(date -Is)"
export DEBIAN_FRONTEND=noninteractive

echo "[bootstrap] atualizando pacotes do Ubuntu"
apt-get update -y
apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold upgrade
apt-get install -y ca-certificates curl gnupg python3

echo "[bootstrap] instalando o Docker Engine (repositório oficial)"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

echo "[bootstrap] instalando a AWS CLI (snap oficial)"
snap install aws-cli --classic || snap refresh aws-cli || true
export PATH="/snap/bin:$PATH"
aws --version

mount_volume() {
  local volume="$1" dir="$2" fallback="$3" id dev=""
  id="\${volume//-/}"
  for _ in $(seq 1 90); do
    if [ -e "/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_\${id}" ]; then dev="/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_\${id}"; break; fi
    if [ -b "$fallback" ]; then dev="$fallback"; break; fi
    sleep 5
  done
  if [ -z "$dev" ]; then echo "[bootstrap] ERRO: o volume $volume não apareceu"; return 1; fi
  dev="$(readlink -f "$dev")"
  if ! blkid "$dev" >/dev/null 2>&1; then
    echo "[bootstrap] formatando $volume (volume novo e vazio)"
    mkfs.ext4 -q "$dev"
  fi
  local uuid
  uuid="$(blkid -s UUID -o value "$dev")"
  mkdir -p "$dir"
  grep -q "UUID=$uuid" /etc/fstab || echo "UUID=$uuid $dir ext4 defaults,nofail,x-systemd.device-timeout=30s 0 2" >> /etc/fstab
  mount "$dir" || mount -a
  echo "[bootstrap] $volume montado em $dir"
}

echo "[bootstrap] montando os volumes de dados"
${mountLines || "true"}

echo "[bootstrap] preparando ${APP_DIR}"
mkdir -p ${APP_DIR} /var/lib/app-bootstrap
${appDirs.map((d) => `mkdir -p ${d}`).join("\n")}
${config.application.volumes.map((v) => `chown -R 1000:1000 ${safe(v.hostPath)}`).join("\n")}
${heredoc(`${APP_DIR}/docker-compose.yml`, renderCompose(config), "644")}${heredoc(`${APP_DIR}/write_env.py`, WRITE_ENV_PY, "644")}${heredoc(
    `${APP_DIR}/deploy.sh`,
    renderDeployScript(input.region, input.ssmPrefix, withDatabase),
    "750",
  )}${heredoc(`${APP_DIR}/status.sh`, STATUS_SCRIPT, "755")}${heredoc("/etc/systemd/system/app.service", renderSystemdUnit(config), "644")}
systemctl daemon-reload
systemctl enable app.service

echo "[bootstrap] primeira publicação (se já houver imagem registrada)"
${APP_DIR}/deploy.sh || echo "[bootstrap] a publicação vai ser feita pelo painel"
touch ${BOOTSTRAP_DONE_FILE}
echo "[bootstrap] concluído $(date -Is)"
`;
}
