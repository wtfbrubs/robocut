# CLAUDE.md — IRL Clip Bot

> Guia de desenvolvimento para o agente de monitoramento de lives IRL, geração automática de cortes e upload no TikTok.

---

## Visão Geral do Projeto

**Nome do projeto:** `irl-clip-bot`
**Objetivo:** Monitorar canais IRL ao vivo (YouTube, Twitch e Kick), detectar momentos relevantes automaticamente, gerar cortes de vídeo no formato vertical (9:16) e fazer upload nas contas do TikTok configuradas.

O bot deve operar de forma contínua, com baixo custo operacional e sem intervenção manual para o fluxo principal.

**Orquestração:** Kubernetes (k8s). A aplicação é estruturada como microserviços independentes — cada etapa do pipeline roda em seu próprio Deployment/Pod, se comunica via fila Redis e compartilha arquivos temporários via PersistentVolume (RWX).

**Infraestrutura alvo:** cluster com 4 nós ARM64 (Ampere A1), 1 OCPU e 6 GB RAM por nó. Total disponível: ~4 OCPU / 24 GB RAM.

---

## Arquitetura Geral

Cada bloco abaixo corresponde a um **microserviço independente** — Deployment próprio no Kubernetes, imagem Docker própria, resource requests/limits individuais.

```
┌─────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                    │
│                  4 × ARM64 (1 OCPU / 6 GB)                  │
│                                                             │
│  [svc-watcher]          [svc-detector]    [svc-clip-worker] │
│  YouTube Watcher ──►    Áudio / Cena ──►  ffmpeg encoder    │
│  Twitch Watcher         Score / Filter    Format 9:16       │
│  Kick Watcher                             Legenda (opt)     │
│        │                     │                  │           │
│        └──────────┬──────────┘                  │           │
│                   ▼                             ▼           │
│            [Redis Queue]              [svc-uploader]        │
│         fila de candidatos ──────►    TikTok API v2         │
│                   │                                         │
│                   ▼                                         │
│            [svc-postgres]                                   │
│           banco de estado                                   │
│                                                             │
│  Shared Storage (PVC RWX)                                   │
│  /mnt/clips — watcher grava, worker lê, uploader lê        │
└─────────────────────────────────────────────────────────────┘
```

### Fluxo de mensagens entre serviços

```
watcher  →  [queue: stream.started]      →  detector
detector →  [queue: clip.candidate]      →  clip-worker
clip-worker → [queue: clip.ready]        →  uploader
uploader →  [queue: upload.done]         →  postgres (via worker)
```

Todos os eventos são mensagens JSON no Redis. Nenhum serviço chama outro diretamente via HTTP — o acoplamento é exclusivamente via fila.

---

## Stack Tecnológica

| Camada              | Tecnologia                                      |
|---------------------|-------------------------------------------------|
| Runtime             | Python 3.11+                                    |
| Gerenciador deps    | `uv` ou `poetry`                                |
| Download de stream  | `yt-dlp`                                        |
| Processamento vídeo | `ffmpeg` (via `ffmpeg-python`)                  |
| Detecção de cenas   | `PySceneDetect` + heurísticas de áudio          |
| Upload TikTok       | TikTok Content Posting API v2                   |
| Fila de mensagens   | `Redis` (Streams ou Lists) + `RQ`               |
| Banco de dados      | PostgreSQL (via SQLAlchemy)                     |
| Orquestração        | **Kubernetes** (manifests em `k8s/`)            |
| Build de imagens    | Docker (multi-stage, `linux/arm64`)             |
| Docker Compose      | apenas para desenvolvimento local               |
| Logs                | `structlog` com saída JSON                      |
| Config              | `ConfigMap` + `Secret` no Kubernetes            |
| Shared storage      | `PersistentVolumeClaim` RWX (`/mnt/clips`)      |

---

## Estrutura de Diretórios

O repositório é um **monorepo** com um serviço por pasta em `services/`. Cada serviço tem seu próprio `Dockerfile` e `pyproject.toml`. Código compartilhado fica em `shared/`.

```
irl-clip-bot/
├── CLAUDE.md
├── README.md
├── docker-compose.dev.yml       # apenas para desenvolvimento local
│
├── shared/                      # biblioteca interna compartilhada entre serviços
│   ├── pyproject.toml
│   └── src/clipbot_shared/
│       ├── models.py            # dataclasses: ClipCandidate, StreamEvent, etc.
│       ├── queue.py             # helpers Redis (publish, consume, ack)
│       ├── db.py                # SQLAlchemy engine + session factory
│       ├── storage.py           # leitura/escrita em /mnt/clips
│       ├── logger.py            # structlog configurado
│       └── retry.py             # decorator de retry com backoff
│
├── services/
│   ├── watcher/                 # svc-watcher — monitora lives
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── src/
│   │       ├── main.py
│   │       ├── base.py
│   │       ├── youtube.py
│   │       ├── twitch.py
│   │       └── kick.py
│   │
│   ├── detector/                # svc-detector — detecta momentos relevantes
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── src/
│   │       ├── main.py
│   │       ├── audio.py
│   │       ├── scene.py
│   │       └── llm.py           # opcional
│   │
│   ├── clip-worker/             # svc-clip-worker — corte e formatação ffmpeg
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── src/
│   │       ├── main.py
│   │       ├── clipper.py
│   │       ├── formatter.py
│   │       └── caption.py       # opcional
│   │
│   └── uploader/                # svc-uploader — upload TikTok
│       ├── Dockerfile
│       ├── pyproject.toml
│       └── src/
│           ├── main.py
│           └── tiktok.py
│
├── k8s/                         # manifests Kubernetes
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml              # não versionar valores reais
│   ├── pvc.yaml                 # shared storage RWX /mnt/clips
│   ├── redis/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   ├── postgres/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── pvc.yaml
│   ├── watcher/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   ├── detector/
│   │   └── deployment.yaml
│   ├── clip-worker/
│   │   └── deployment.yaml      # nodeAffinity: nós 3 e 4
│   └── uploader/
│       └── deployment.yaml
│
├── config/
│   ├── channels.yaml            # lista de canais monitorados
│   └── settings.py
│
└── scripts/
    ├── add_channel.py
    └── manual_clip.py
```

---

## Módulos — Comportamento Esperado

### `watchers/`

- Cada watcher implementa `BaseWatcher` com os métodos:
  - `is_live() -> bool`
  - `get_stream_url() -> str`  
  - `get_metadata() -> dict` (título, streamer, categoria, thumbnail)
- O polling deve ocorrer a cada **30–60 segundos** por canal.
- Quando uma live é detectada, emite um evento `StreamStarted` para a fila.
- Quando a live encerra, emite `StreamEnded` e persiste o estado no banco.
- Nunca lançar exceção não tratada: logar o erro e continuar o loop.

**Twitch:** usar `twitchAPI` ou chamadas diretas à Helix API com OAuth client credentials.  
**YouTube:** usar `yt-dlp` para verificar se o canal está ao vivo (`--skip-download --print is_live`).  
**Kick:** usar a API pública de Kick (`https://kick.com/api/v1/channels/{slug}`), sem autenticação necessária para leitura.

---

### `detector/`

O objetivo é identificar **janelas de tempo** dentro da live que merecem virar um corte.

**Estratégias implementadas (em ordem de prioridade):**

1. **Detecção de áudio (hype):** analisar o buffer de áudio em tempo real. Picos de volume acima de um threshold por N segundos consecutivos indicam momento relevante (grito, reação, etc.).
2. **Detecção de cena:** mudanças bruscas de cena (`PySceneDetect`) podem indicar corte natural.
3. **Janela fixa:** fallback — a cada X minutos de live, gerar um corte do trecho mais recente.
4. **(Opcional/Futuro)** Transcrição via `faster-whisper` + análise de sentimento para detectar momentos engraçados/dramáticos.

Cada momento detectado gera um objeto `ClipCandidate`:
```python
@dataclass
class ClipCandidate:
    channel_id: str
    platform: str
    start_ts: float       # timestamp em segundos dentro da live
    end_ts: float
    score: float          # 0.0 a 1.0 — confiança/relevância
    reason: str           # "audio_spike" | "scene_change" | "scheduled"
```

Candidatos com `score < CLIP_MIN_SCORE` (configurável) são descartados.

---

### `pipeline/`

**`clipper.py`**
- Recebe um `ClipCandidate` + URL do stream gravado/segmento.
- Usa `ffmpeg` para extrair o trecho com re-encode mínimo (`-c copy` quando possível).
- Duração máxima do clipe: **60 segundos** (limite TikTok para upload via API básica). Configurável via `CLIP_MAX_DURATION`.
- Duração mínima: **10 segundos**.
- Salva em `/tmp/clips/{uuid}.mp4`.

**`formatter.py`**
- Converte o vídeo para formato vertical **1080x1920** (9:16).
- Se o vídeo original for landscape (16:9), aplica `crop` centralizado + `scale`, com blur nas laterais (efeito "pillarbox blur") como padrão.
- Aplica marca d'água/watermark configurável (logo PNG com transparência).
- Output: H.264, AAC, bitrate de vídeo `4M`, áudio `192k`.

**`caption.py`** *(opcional, ativado via flag)*
- Transcreve o áudio do clipe com `faster-whisper` (modelo `small` ou `medium`).
- Gera legendas em formato SRT e as queima no vídeo (`ffmpeg -vf subtitles`).
- Estilo de legenda: fonte grande, centralizada na parte inferior, com outline — padrão "TikTok viral".

---

### `uploader/tiktok.py`

- Usar a **TikTok Content Posting API v2** (requer aprovação de app TikTok Developer).
- Fluxo de upload:
  1. `POST /v2/post/publish/video/init/` — inicializa o upload, obtém `upload_url` e `publish_id`.
  2. Upload do arquivo de vídeo para o `upload_url` via PUT com chunks.
  3. `GET /v2/post/publish/status/fetch/` — polling do status até `PUBLISH_COMPLETE` ou erro.
- Suporte a múltiplas contas TikTok: cada conta tem seu `access_token` armazenado no banco, associado a um `tiktok_account_id`.
- Geração automática de título/caption: `f"🔴 {streamer_name} | {clip_reason} #{platform} #IRL #live"` — customizável.
- Hashtags configuráveis por canal no `channels.yaml`.
- Rate limit: respeitar o limite de posts por dia por conta (máx. ~50/dia na API padrão). Controlar com contador no banco.

---

### `db/models.py`

Tabelas principais:

```
channels         → id, platform, channel_id, slug, name, active, tiktok_account_id
stream_sessions  → id, channel_id, started_at, ended_at, stream_url
clip_candidates  → id, session_id, start_ts, end_ts, score, reason, status
clips            → id, candidate_id, file_path, duration, processed_at, status
uploads          → id, clip_id, tiktok_account_id, publish_id, status, uploaded_at, tiktok_url
```

---

## Configuração — `channels.yaml`

```yaml
channels:
  - platform: twitch
    slug: nomeDoCanalTwitch
    name: "Nome do Streamer"
    tiktok_account: conta_tiktok_1
    hashtags: ["#twitch", "#IRL", "#live", "#clip"]
    clip_min_score: 0.6

  - platform: youtube
    channel_id: UCxxxxxxxxxxxx
    name: "Nome do Canal"
    tiktok_account: conta_tiktok_2
    hashtags: ["#youtube", "#IRL"]
    clip_min_score: 0.5

  - platform: kick
    slug: nomeDoCanalKick
    name: "Nome do Streamer"
    tiktok_account: conta_tiktok_1
    hashtags: ["#kick", "#IRL", "#live"]
    clip_min_score: 0.65
```

---

## Variáveis de Ambiente — `.env.dev` (desenvolvimento local)

Em produção as variáveis vêm do `ConfigMap` e `Secret` do Kubernetes. O arquivo abaixo é apenas para `docker-compose.dev.yml`.

```dotenv
# Geral
LOG_LEVEL=INFO
CLIP_MAX_DURATION=60
CLIP_MIN_DURATION=10
CLIP_MIN_SCORE=0.55
ENABLE_CAPTIONS=false
CLIPS_DIR=/mnt/clips

# Twitch
TWITCH_CLIENT_ID=
TWITCH_CLIENT_SECRET=

# YouTube (yt-dlp, sem auth necessária para lives públicas)
YOUTUBE_COOKIES_FILE=./config/youtube_cookies.txt   # opcional

# TikTok
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_ACCESS_TOKEN_CONTA1=
TIKTOK_ACCESS_TOKEN_CONTA2=

# Banco de Dados
DATABASE_URL=postgresql://clipbot:devpassword@postgres:5432/clipbot

# Redis
REDIS_URL=redis://redis:6379/0
```

---

## Kubernetes — Manifests e Convenções

### Namespace

Todos os recursos ficam no namespace `clipbot`:

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: clipbot
```

---

### ConfigMap e Secret

Configurações não-sensíveis no `ConfigMap`; credenciais no `Secret`.

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: clipbot-config
  namespace: clipbot
data:
  LOG_LEVEL: "INFO"
  CLIP_MAX_DURATION: "60"
  CLIP_MIN_DURATION: "10"
  CLIP_MIN_SCORE: "0.55"
  ENABLE_CAPTIONS: "false"
  CLIPS_DIR: "/mnt/clips"
  REDIS_URL: "redis://redis-svc:6379/0"
  DATABASE_URL: "postgresql://clipbot:$(POSTGRES_PASSWORD)@postgres-svc:5432/clipbot"
```

```yaml
# k8s/secret.yaml  (valores em base64 — nunca versionar o arquivo com valores reais)
apiVersion: v1
kind: Secret
metadata:
  name: clipbot-secrets
  namespace: clipbot
type: Opaque
stringData:
  TWITCH_CLIENT_ID: ""
  TWITCH_CLIENT_SECRET: ""
  TIKTOK_CLIENT_KEY: ""
  TIKTOK_CLIENT_SECRET: ""
  TIKTOK_ACCESS_TOKEN_CONTA1: ""
  POSTGRES_PASSWORD: ""
```

---

### PersistentVolumeClaim — Shared Storage

O volume `/mnt/clips` é compartilhado entre `watcher`, `clip-worker` e `uploader`. Requer `ReadWriteMany` — usar NFS, OCI File Storage ou `local-path` com NFS overlay.

```yaml
# k8s/pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: clips-pvc
  namespace: clipbot
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 50Gi
  storageClassName: nfs  # ajustar para o StorageClass disponível no cluster
```

---

### Deployments por Serviço

#### Resource requests/limits (ARM64 — baseado no cluster 4×1OCPU/6GB)

| Serviço       | CPU request | CPU limit | RAM request | RAM limit | Réplicas |
|---------------|-------------|-----------|-------------|-----------|----------|
| watcher       | 150m        | 400m      | 384Mi       | 768Mi     | 1        |
| detector      | 200m        | 600m      | 512Mi       | 1Gi       | 1        |
| clip-worker   | 600m        | 950m      | 768Mi       | 1.5Gi     | 2        |
| uploader      | 100m        | 200m      | 128Mi       | 256Mi     | 1        |
| redis         | 100m        | 300m      | 128Mi       | 256Mi     | 1        |
| postgres      | 150m        | 400m      | 512Mi       | 1Gi       | 1        |

#### Exemplo — clip-worker (serviço mais crítico)

```yaml
# k8s/clip-worker/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: clip-worker
  namespace: clipbot
spec:
  replicas: 2
  selector:
    matchLabels:
      app: clip-worker
  template:
    metadata:
      labels:
        app: clip-worker
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: clipbot/role
                    operator: In
                    values: ["encoder"]          # label nos nós 3 e 4
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector:
                matchLabels:
                  app: clip-worker
              topologyKey: kubernetes.io/hostname # 1 worker por nó
      containers:
        - name: clip-worker
          image: ghcr.io/seu-usuario/irl-clip-worker:latest
          imagePullPolicy: Always
          envFrom:
            - configMapRef:
                name: clipbot-config
            - secretRef:
                name: clipbot-secrets
          resources:
            requests:
              cpu: "600m"
              memory: "768Mi"
            limits:
              cpu: "950m"
              memory: "1536Mi"
          volumeMounts:
            - name: clips
              mountPath: /mnt/clips
          livenessProbe:
            exec:
              command: ["python", "-c", "import sys; sys.exit(0)"]
            initialDelaySeconds: 10
            periodSeconds: 30
      volumes:
        - name: clips
          persistentVolumeClaim:
            claimName: clips-pvc
```

---

### Node Labels — Separação de Workloads

Aplicar labels nos nós para que o `nodeAffinity` funcione:

```bash
# nós 1 e 2: workloads leves (watcher, detector, redis, postgres)
kubectl label node <node-1> clipbot/role=general
kubectl label node <node-2> clipbot/role=general

# nós 3 e 4: encoding pesado (clip-worker isolado)
kubectl label node <node-3> clipbot/role=encoder
kubectl label node <node-4> clipbot/role=encoder
```

---

### PriorityClass

Garantir que o `watcher` nunca seja evicted em situação de pressão de recursos:

```yaml
# k8s/priorityclass.yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: clipbot-critical
value: 1000000
globalDefault: false
description: "Watchers e Redis — não podem ser interrompidos"
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: clipbot-worker
value: 500000
globalDefault: false
description: "clip-worker e uploader — podem aguardar"
```

Adicionar em cada Deployment:
```yaml
spec:
  template:
    spec:
      priorityClassName: clipbot-critical  # ou clipbot-worker
```

---

### Docker Compose (desenvolvimento local)

Usado apenas para rodar localmente sem cluster. Não é o método de deploy em produção.

```yaml
# docker-compose.dev.yml
version: "3.9"
services:
  watcher:
    build: ./services/watcher
    env_file: .env.dev
    volumes:
      - ./config:/app/config
      - clips_tmp:/mnt/clips
    depends_on: [redis]

  detector:
    build: ./services/detector
    env_file: .env.dev
    volumes:
      - clips_tmp:/mnt/clips
    depends_on: [redis]

  clip-worker:
    build: ./services/clip-worker
    env_file: .env.dev
    volumes:
      - clips_tmp:/mnt/clips
    depends_on: [redis]

  uploader:
    build: ./services/uploader
    env_file: .env.dev
    volumes:
      - clips_tmp:/mnt/clips
    depends_on: [redis, postgres]

  redis:
    image: redis:7-alpine
    volumes: [redis_data:/data]

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: clipbot
      POSTGRES_USER: clipbot
      POSTGRES_PASSWORD: devpassword
    volumes: [pg_data:/var/lib/postgresql/data]

volumes:
  clips_tmp:
  redis_data:
  pg_data:
```

---

## Regras de Desenvolvimento

### Geral
- Python 3.11+. Sem f-strings em logging (`%s` ou `structlog`).
- Toda função com I/O externo deve ter timeout explícito.
- Usar `async/await` onde possível (watchers, uploader).
- Erros de API externa: logar com contexto completo, nunca silenciar.
- Não commitar tokens, chaves ou cookies. Usar `Secret` do Kubernetes ou `.env.dev` local (gitignored).

### Microserviços — contratos entre serviços
- Nenhum serviço importa código de outro serviço diretamente. Dependências cruzadas só via `shared/`.
- A comunicação entre serviços é **exclusivamente via Redis queue** — sem chamadas HTTP síncronas entre pods.
- Toda mensagem na fila é um JSON com `event_type`, `payload` e `trace_id`. O `trace_id` deve ser propagado em todos os logs para rastreabilidade end-to-end.
- Cada serviço deve ser capaz de reiniciar sem perda de estado — o estado fica no Redis (fila) e no PostgreSQL, nunca em memória entre reinicios.
- Consumers Redis devem usar `BLPOP` com timeout (não busy-loop) e recolocar a mensagem na fila em caso de falha não recuperável (dead-letter queue `queue:dlq`).

### Kubernetes
- Todo Deployment deve ter `livenessProbe` e `readinessProbe` configurados.
- Nunca usar `latest` como tag de imagem em produção. Usar digest SHA ou tag semântica (`v1.2.3`).
- `resources.requests` e `resources.limits` são obrigatórios em todos os containers — sem eles o scheduler ARM não aloca corretamente.
- Secrets nunca no repositório. Usar `stringData` em arquivo local e aplicar via `kubectl apply` ou substituir por solução de secrets management (ex: Sealed Secrets ou External Secrets Operator).
- Usar `kubectl rollout status` para validar deploys antes de considerar concluído.
- Alterações em `ConfigMap` requerem rollout manual dos pods (`kubectl rollout restart deployment/<name>`).

### Docker / ARM64
- Todas as imagens devem ser buildadas para `linux/arm64`:
  ```bash
  docker buildx build --platform linux/arm64 -t image:tag .
  ```
- Usar imagens base com suporte ARM explícito: `python:3.11-slim`, `redis:7-alpine`, `postgres:16-alpine` — todas têm manifests ARM64.
- O `ffmpeg` deve ser instalado via `apt` na imagem do `clip-worker` (não via pip): `apt-get install -y ffmpeg`. Verificar que o binário é ARM64 nativo (`file $(which ffmpeg)`).
- Nunca usar imagens x86 com emulação QEMU no cluster de produção — degradação de performance de 3–5×.
- Builds multi-stage obrigatórios para reduzir tamanho final da imagem:
  ```dockerfile
  FROM python:3.11-slim AS builder
  # instala deps
  FROM python:3.11-slim AS runtime
  # copia apenas o necessário
  ```

### ffmpeg (no contexto Kubernetes)
- Sempre especificar `-loglevel warning` para não poluir os logs.
- Usar `-movflags +faststart` no output para streaming web.
- Validar que o arquivo de output existe e tem tamanho > 0 após cada operação.
- Forçar `-threads 1` em todos os jobs no cluster ARM — evita contenção com o `cpu limit` do container:
  ```bash
  ffmpeg -threads 1 -i input.ts -vf scale=1080:1920 -preset veryfast -crf 28 -threads 1 output.mp4
  ```
- Path de input/output sempre dentro de `/mnt/clips/{trace_id}/` para isolamento por job.
- Limpar o diretório do job após upload concluído — não depender de cron externo.

### TikTok API
- Nunca hardcodar `access_token`. Sempre buscar do `Secret` Kubernetes via env var.
- Implementar refresh de token quando a API retornar `401`.
- Respeitar o campo `retry_after` em respostas `429`.
- Todo upload deve ser registrado na tabela `uploads` antes de iniciar (estado `pending`).

### Testes
- Mockar chamadas externas (yt-dlp, ffmpeg, TikTok API, Redis) nos testes unitários.
- Testes de integração devem rodar apenas com flag `--integration` e variáveis de ambiente reais.
- Cobertura mínima alvo: **70%** nos módulos `detector/` e `pipeline/`.
- Cada serviço tem seus próprios testes em `services/<nome>/tests/`.

### Logs
- Todo evento relevante deve logar: `platform`, `channel`, `clip_id`, `trace_id`, `status`, `service`.
- Exemplo de log estruturado:
  ```json
  {"event": "clip_uploaded", "service": "uploader", "platform": "twitch", "channel": "xpto", "clip_id": "abc123", "trace_id": "uuid4", "tiktok_url": "https://tiktok.com/...", "duration": 42.3}
  ```
- Em Kubernetes, logs em JSON são coletados diretamente pelo agregador (ex: Loki, CloudWatch). Não usar formato multiline.

---

## Limitações Conhecidas e Contornos

| Limitação | Contorno |
|---|---|
| TikTok API exige aprovação de app | Criar app em developers.tiktok.com com caso de uso "Content Posting" |
| YouTube não expõe stream HLS diretamente | Usar `yt-dlp` para resolver a URL do stream ao vivo |
| Kick não tem API oficial completa | Usar endpoints públicos não documentados (sujeito a mudança) |
| ffmpeg não processa stream diretamente de URL m3u8 em alguns casos | Baixar segmentos com `yt-dlp` para buffer local em `/mnt/clips` antes de processar |
| TikTok limita uploads por dia | Controlar contador no banco; distribuir entre múltiplas contas se necessário |
| PVC RWX requer StorageClass com suporte a NFS | Configurar NFS no cluster ou usar OCI File Storage com driver CSI |
| ARM64: imagens sem suporte nativo travam com QEMU | Verificar manifests multi-arch antes de usar qualquer imagem base nova |
| 1 OCPU por nó limita paralelismo de encoding | Máximo 1 job ffmpeg por nó; usar `podAntiAffinity` para garantir distribuição |

---

## Roadmap Sugerido

**Fase 1 — MVP**
- [ ] Watcher funcional para Twitch (serviço isolado)
- [ ] Detecção por janela fixa (a cada 10 min)
- [ ] Pipeline ffmpeg: corte + resize 9:16
- [ ] Upload manual (script `manual_clip.py`)
- [ ] Integração TikTok API (1 conta)
- [ ] Docker Compose dev funcional com todos os serviços

**Fase 2 — Automação**
- [ ] Watchers para YouTube e Kick
- [ ] Detecção por pico de áudio
- [ ] Upload automático ao final do pipeline
- [ ] Fila Redis com dead-letter queue
- [ ] Deploy no Kubernetes com manifests em `k8s/`
- [ ] PVC RWX configurado e validado entre pods
- [ ] Node labels e `nodeAffinity` para clip-worker

**Fase 3 — Resiliência e Qualidade**
- [ ] `livenessProbe` e `readinessProbe` em todos os Deployments
- [ ] `PriorityClass` configurado para proteger watchers
- [ ] Legendas automáticas (faster-whisper)
- [ ] Suporte a múltiplas contas TikTok
- [ ] Alertas de erro (via Telegram bot ou webhook)
- [ ] HorizontalPodAutoscaler no clip-worker (baseado em tamanho da fila Redis)
- [ ] Detecção por LLM/visão computacional (opcional)

---

## Referências

- [TikTok Content Posting API](https://developers.tiktok.com/doc/content-posting-api-get-started)
- [yt-dlp docs](https://github.com/yt-dlp/yt-dlp)
- [PySceneDetect](https://www.scenedetect.com/docs/)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [ffmpeg-python](https://github.com/kkroening/ffmpeg-python)
- [Twitch Helix API — Streams](https://dev.twitch.tv/docs/api/reference/#get-streams)
- [Kick Public API](https://kick.com/api/v1/channels/{slug})
- [Kubernetes — Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Kubernetes — nodeAffinity](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/)
- [Kubernetes — PriorityClass](https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/)
- [Docker Buildx — multi-platform ARM64](https://docs.docker.com/buildx/working-with-buildx/)
- [OCI File Storage CSI Driver](https://github.com/oracle/oci-cloud-controller-manager/blob/master/docs/file-system-setup.md)