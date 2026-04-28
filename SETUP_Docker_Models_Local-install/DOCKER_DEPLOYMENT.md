# TranscrevAI - Docker Deployment

Aplicacao de transcricao e diarizacao de audio com modelos ML embedded.

**Suporte Multi-Arquitetura:** AMD64 (Intel/AMD) e ARM64 (Apple Silicon)

---

## Como Rodar (Testadores / Recrutadores)

### Pre-requisitos

- Docker e Docker Compose
- ~25GB de espaco em disco

### Comandos

```bash
# Opcao 1 — Sem clonar o repositorio (mais simples)
curl -L https://raw.githubusercontent.com/hiperim/transcrevai/main/docker-compose.pull.yml -o docker-compose.yml && docker compose up
```

```bash
# Opcao 2 — Com o codigo clonado
git clone https://github.com/hiperim/transcrevai.git
cd transcrevai
docker compose -f docker-compose.pull.yml up
```

### Acesso

http://localhost:8000

---

## Detalhes

- **Imagem:** ~20GB (modelos ML embedded)
- **Download:** Automatico do Docker Hub
- **Token HF:** Nao necessario
- **Internet:** Apenas para download inicial
- **Performance:** Auto-detecta CPU/RAM disponiveis

### Comandos Uteis

```bash
# Rodar em background
docker compose -f docker-compose.pull.yml up -d

# Forcar pull da imagem mais recente e subir
docker compose -f docker-compose.pull.yml up -d --pull always

# Ver logs
docker compose -f docker-compose.pull.yml logs -f

# Parar
docker compose -f docker-compose.pull.yml down
```

---

## Build e Push (Para Mantenedores)

### Pre-requisitos

- Docker Desktop com Buildx
- `.env` com `HUGGING_FACE_HUB_TOKEN=hf_xxx`
- Login no Docker Hub: `docker login`

### Processo completo (Windows PowerShell)

**1. Carregar variaveis de ambiente do .env:**

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^(?<name>.*?)=(?<value>.*)$') {
        $name = $Matches['name'].Trim()
        $value = $Matches['value'].Trim().Trim('"').Trim("'")
        [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}
```

**2. Recriar builder do zero (evita cache de builds anteriores):**

```powershell
docker buildx rm multiarch-fixed --force
docker buildx create --name multiarch-fixed --driver docker-container --buildkitd-config C:\transcrevai\buildkitd.toml --use
docker buildx inspect --bootstrap
```

O `buildkitd.toml` configura DNS externo (8.8.8.8 / 1.1.1.1) para o container buildkit conseguir fazer push ao Docker Hub.

**3. Build e push (AMD64 + ARM64, sem cache):**

```powershell
docker buildx build --platform linux/amd64,linux/arm64 --no-cache -t hiperim/transcrevai:latest --push -f Dockerfile.multiarch .
```

### Usando o script automatizado

```powershell
.\SETUP_Docker_Models_Local-install\build-multiarch.ps1
```

O script faz os 3 passos acima de forma interativa.

---

## Atualizar imagem no servidor

Apos novo build e push, no servidor:

```bash
docker compose -f docker-compose.pull.yml up -d --pull always
```

---

## Notas

- `--no-cache` garante build limpo sem reuso de layers anteriores
- O builder `multiarch-fixed` deve ser recriado do zero a cada build para evitar problemas de cache e DNS
- A imagem atual e `linux/amd64` + `linux/arm64` — Docker seleciona automaticamente a arquitetura correta no pull
- Para buildar so AMD64 (mais rapido): substituir `linux/amd64,linux/arm64` por `linux/amd64`
