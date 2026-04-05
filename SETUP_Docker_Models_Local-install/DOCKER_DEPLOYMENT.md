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

# Ver logs
docker compose -f docker-compose.pull.yml logs -f

# Parar
docker compose -f docker-compose.pull.yml down
```

---

## Build Local (Para Desenvolvedores)

1. Crie `.env` com token HF:
   ```
   HUGGING_FACE_HUB_TOKEN=hf_xxx
   ```

2. Baixe os modelos de IA/ML (~3-5GB):
   ```bash
   python SETUP_Docker_Models_Local-install/download_models.py
   ```

3. Execute o build:
   ```bash
   # Windows
   .\SETUP_Docker_Models_Local-install\build-multiarch.ps1

   # Linux/Mac
   ./SETUP_Docker_Models_Local-install/build-multiarch.sh
   ```
