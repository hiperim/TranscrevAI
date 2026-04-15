# Diretório de Scripts de Setup

Este diretório contém scripts para build de imagens Docker e download de modelos.

---

## Quick Start (Usuarios)

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

Acesso: http://localhost:8000

- Imagem (~20GB) baixada automaticamente do Docker Hub
- Modelos ML embedded — token nao necessario
- Hardware detectado automaticamente para performance otima

---

## Para Desenvolvedores

### Download de Modelos (Build Local)

**`download_models.py`** - Baixa modelos Whisper e Pyannote

```bash
# Requer HUGGING_FACE_HUB_TOKEN em .env
python download_models.py
```

### Docker Build Scripts (Multi-Arquitetura)

Scripts para build de imagens que funcionam em Intel/AMD (x86_64) e Apple Silicon (ARM64):

| Script | Plataforma |
|--------|------------|
| `build-multiarch.ps1` | Windows PowerShell |
| `build-multiarch.sh` | Linux/macOS |

**Requer:** Docker Desktop, token Hugging Face em `.env`

```bash
# Windows
.\build-multiarch.ps1

# Linux/Mac
chmod +x ./build-multiarch.sh
./build-multiarch.sh
```

---

## Documentacao

- **[DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)** - Guia de deployment Docker

---

Para duvidas, consulte o [README.md](../README.md) principal do projeto.

---

# Setup Scripts Directory

This directory contains scripts for building Docker images and downloading models.

---

## Quick Start (Users)

```bash
# Option 1 — Without cloning the repository (simpler)
curl -L https://raw.githubusercontent.com/hiperim/transcrevai/main/docker-compose.pull.yml -o docker-compose.yml && docker compose up
```

```bash
# Option 2 — With cloned code
git clone https://github.com/hiperim/transcrevai.git
cd transcrevai
docker compose -f docker-compose.pull.yml up
```

Access: http://localhost:8000

- Image (~20GB) downloads automatically from Docker Hub
- All ML models embedded - no token needed
- Hardware auto-detected for optimal performance

---

## For Developers

### Download Models (Local Build)

**`download_models.py`** - Downloads Whisper and Pyannote models

```bash
# Requires HUGGING_FACE_HUB_TOKEN in .env
python download_models.py
```

### Docker Build Scripts (Multi-Architecture)

Scripts to build images that work on Intel/AMD (x86_64) and Apple Silicon (ARM64):

| Script | Platform |
|--------|----------|
| `build-multiarch.ps1` | Windows PowerShell |
| `build-multiarch.sh` | Linux/macOS |

**Requires:** Docker Desktop, Hugging Face token in `.env`

```bash
# Windows
.\build-multiarch.ps1

# Linux/Mac
chmod +x ./build-multiarch.sh
./build-multiarch.sh
```

---

## Documentation

- **[DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)** - Docker deployment guide

---

For questions or issues, see the main project [README.md](../README.md).
