# TranscrevAI - Transcrição e diarização de áudio 100% local, sem APIs externas

  <p align="center">
    <img width="577" height="1030" alt="TranscrevAI_preview" src="https://github.co
  m/user-attachments/assets/60c74d79-57e4-4378-8045-45940e19355f" />
  </p>


## Visão Geral

O TranscrevAI é uma aplicação de alto desempenho para transcrição de áudio e diarização de locutores. Ela recebe um áudio como entrada e fornece uma transcrição completa, identificando quem disse o quê e quando. Foi projetada para ser uma ferramenta poderosa para quem precisa de transcrições rápidas e precisas de conversas, reuniões ou gravações.

Toda a transcrição ocorre localmente na máquina onde o servidor está rodando, sem o uso de nenhuma API externa, garantindo a privacidade dos dados. Esta arquitetura offline alinha-se fortemente com os princípios de segurança e minimização de dados expostos da Lei Geral de Proteção de Dados brasileira (LGPD).

## Funcionalidades

- **Transcrição de Alto Desempenho:** Utiliza o modelo faster-whisper para transcrição local e rápida (implementação otimizada do Whisper da OpenAI para CPU)
- **Diarização de Locutores:** Identifica diferentes locutores no áudio usando pyannote.audio com algoritmo word-level alignment
- **Gravação ao Vivo:** Permite a gravação de áudio diretamente no navegador, com buffering em disco para suportar gravações longas sem consumir excesso de RAM
- **Upload de Arquivos:** Suporta o upload de arquivos de áudio pré-gravados
- **Geração de Legendas .srt:** Cria arquivos de legenda para vídeos
- **Geração de Vídeos .mp4:** Produz vídeos com legendas embutidas sobre um fundo preto
- **Atualizações de Progresso em Tempo Real:** Interface WebSocket com monitoramento do progresso pelo usuário

## Tecnologias Utilizadas

- **Backend:** Python 3.11, FastAPI
- **Modelos de IA/ML:**
    - **Transcrição:** faster-whisper (Whisper medium otimizado para CPU)
    - **Diarização:** pyannote.audio 3.1
- **Biblioteca Principal de ML:** PyTorch (CPU-only, INT8 quantization)
- **Comunicação em Tempo Real:** WebSockets
- **Processamento de Áudio/Vídeo:** FFmpeg, librosa
- **Deployment:** Docker, Gunicorn/Uvicorn
- **SSL/HTTPS:** Cloudflare Tunnel + certificado automático

## Arquitetura

A aplicação é construída sobre o FastAPI e segue uma arquitetura moderna baseada em Injeção de Dependência (DI), garantindo que os componentes sejam modulares, estáveis e geridos de forma eficiente.

- **Serviços Modulares:** Cada funcionalidade principal é encapsulada num serviço (TranscriptionService, PyannoteDiarizer, LiveAudioProcessor, SessionManager)
- **Gestão de Sessões:** Ciclo de vida completo de cada sessão de utilizador com limpeza automática (timeout de 24h)
- **Processamento Assíncrono:** Tarefas pesadas executadas em worker threads separados para não bloquear o servidor principal
- **Buffering em Disco:** Gravações longas armazenadas temporariamente em disco, permitindo baixo consumo de memória
- **Otimização Adaptativa:** Detecção automática de hardware (CPU cores, RAM) e alocação dinâmica de threads

## Performance

**Métricas alcançadas:**
- **Startup time:** <30s com pre-loading de modelos
- **Memory usage:** ~2GB peak (otimizado para sistemas com 8GB RAM)
- **Processing ratio:** ~1.5x realtime
- **Accuracy PT-BR:** 90%+ com correções linguísticas pós-processamento
- **Architecture:** CPU-only com INT8 quantization para compatibilidade universal

---

## Instalação e Uso

### Demonstração Online

**Acesse: https://transcrevai.online**

Teste o TranscrevAI diretamente no navegador sem instalar nada.

**Características:**
- HTTPS automático via Cloudflare
- Todas as funcionalidades disponíveis (transcrição, diarização, gravação ao vivo)
- Ideal para avaliação rápida do sistema

**Nota:** Esta é uma instância de demonstração rodando em hardware próprio. Para uso em produção ou desenvolvimento, instale localmente.

---

## Opção 1 — Docker (Recomendado para Testadores e Recrutadores)

A forma mais simples de rodar o TranscrevAI. Não requer Python, FFmpeg ou token do Hugging Face.

**Pré-requisitos:** Docker Desktop instalado e rodando. ~25GB de espaço em disco.

### Sem clonar o repositório

```bash
curl -L https://raw.githubusercontent.com/hiperim/transcrevai/main/docker-compose.pull.yml -o docker-compose.yml
docker compose up
```

### Com o repositório clonado

```bash
git clone https://github.com/hiperim/transcrevai.git
cd transcrevai
docker compose -f docker-compose.pull.yml up
```

### Acesso

```
http://localhost:8000
```

A imagem (~20GB com modelos ML embedded) é baixada automaticamente do Docker Hub na primeira execução. Execuções seguintes iniciam instantaneamente.

### Comandos úteis

```bash
# Rodar em background
docker compose -f docker-compose.pull.yml up -d

# Ver logs
docker compose -f docker-compose.pull.yml logs -f

# Parar
docker compose -f docker-compose.pull.yml down
```

---

## Opção 2 — Instalação Local (Para Desenvolvimento)

**Requer Python 3.11+, FFmpeg e token Hugging Face.**

1. Clone o repositório:
   ```bash
   git clone https://github.com/hiperim/transcrevai.git
   cd transcrevai
   ```

2. Crie e ative ambiente virtual:
   ```bash
   python -m venv venv

   # Windows
   .\venv\Scripts\activate

   # Linux/Mac
   source venv/bin/activate
   ```

3. Instale dependências:
   ```bash
   # Produção
   pip install -r requirements.txt

   # Desenvolvimento (inclui pytest)
   pip install -r requirements-dev.txt
   ```

4. Configure token no `.env`:
   ```bash
   HUGGING_FACE_HUB_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```

5. Download dos modelos de IA/ML:
   ```bash
   python Certification_SSL_ModelsCache/download_models.py
   ```

   Este comando baixa (~3-5GB):
   - faster-whisper-medium (transcrição)
   - pyannote/speaker-diarization-3.1
   - pyannote/segmentation-3.0
   - pyannote/wespeaker embeddings

6. Executar aplicação:
   ```bash
   python main.py
   ```

7. Acessar: `http://localhost:8000`

---

## Configuração HTTPS Local (Opcional)

Esta seção é relevante **somente** se você quiser rodar o app localmente com HTTPS (`https://localhost`). Para uso normal via `http://localhost:8000` isso não é necessário.

A necessidade surge da API `getUserMedia()` do navegador, que em alguns contextos exige HTTPS para captura de áudio ao vivo.

Execute o script automatizado:
```batch
# Windows (como Administrador)
.\Certification_SSL_ModelsCache\setup_dev_certs.bat
```

Este script instala mkcert e gera certificados locais confiáveis para `https://localhost:8000`.

**Documentação completa:** [SSL_SETUP.md](./Certification_SSL_ModelsCache/SSL_SETUP.md)

---

## Testes

A aplicação inclui suite completa de testes:

```bash
# Todos os testes
pytest

# Testes específicos
pytest tests/test_services.py
pytest tests/test_accuracy_performance.py
pytest tests/test_live_server.py

# Com coverage
pytest --cov=src tests/
```

**Testes incluem:**
- Testes unitários com mocks
- Testes de integração com servidor real
- Métricas de qualidade (WER/CER)
- Monitoramento de uso de memória

---

## Documentação Técnica

- **[DOCKER_DEPLOYMENT.md](./SETUP_Docker_Models_Local-install/DOCKER_DEPLOYMENT.md)** - Guia completo de deployment Docker
- **[SSL_SETUP.md](./Certification_SSL_ModelsCache/SSL_SETUP.md)** - Configuração HTTPS para desenvolvimento
- **[pipeline_workflow.md](./pipeline_workflow.md)** - Diagrama detalhado do fluxo de processamento

---

## Estrutura do Projeto

```
transcrevai/
├── src/                                    # Código fonte principal
│   ├── transcription.py                    # Serviço de transcrição (faster-whisper)
│   ├── diarization.py                      # Serviço de diarização (pyannote)
│   ├── audio_processing.py                 # Processamento de áudio e sessões
│   ├── pipeline.py                         # Orquestração do pipeline completo
│   ├── dependencies.py                     # Injeção de dependências
│   ├── exceptions.py                       # Hierarquia de exceções customizadas
│   ├── file_manager.py                     # Gestão de arquivos e storage
│   └── websocket_handler.py                # Validação WebSocket
├── tests/                                  # Suite de testes
│   ├── test_services.py                    # Testes unitários
│   ├── test_accuracy_performance.py        # Testes de accuracy e performance
│   ├── test_live_server.py                 # Testes de integração
│   ├── metrics.py                          # Cálculos WER/CER
│   ├── utils.py                            # Utilitários de teste
│   └── conftest.py                         # Pytest fixtures
├── config/                                 # Configuração da aplicação
│   └── app_config.py                       # AppConfig com validação
├── static/                                 # Frontend (JavaScript, CSS)
├── templates/                              # Templates HTML (Jinja2)
├── Certification_SSL_ModelsCache/          # SSL e cache de modelos
│   ├── download_models.py                  # Download automático de modelos
│   ├── setup_dev_certs.bat                 # Setup SSL desenvolvimento
│   └── SSL_SETUP.md                        # Guia de configuração SSL
├── SETUP_Docker_Models_Local-install/      # Scripts de build Docker
│   ├── build-multiarch.ps1                 # Build Docker multi-arch (Windows)
│   ├── build-multiarch.sh                  # Build Docker multi-arch (Linux/Mac)
│   └── DOCKER_DEPLOYMENT.md               # Guia de deployment Docker
├── Dockerfile.multiarch                    # Imagem Docker multi-arch (AMD64+ARM64)
├── docker-compose.yml                      # Build local (requer token HF)
├── docker-compose.pull.yml                 # Pull do Docker Hub (sem token)
├── pytest.ini                              # Configuração pytest
├── pyrightconfig.json                      # Type checking
└── main.py                                 # Entry point da aplicação
```

---

## Configuração via Variáveis de Ambiente

```bash
# Servidor
TRANSCREVAI_HOST=0.0.0.0
TRANSCREVAI_PORT=8000

# SSL (opcional - desenvolvimento local)
TRANSCREVAI_SSL_CERT=certs/localhost.pem
TRANSCREVAI_SSL_KEY=certs/localhost-key.pem

# Modelo
TRANSCREVAI_MODEL_NAME=medium
TRANSCREVAI_DEVICE=cpu
TRANSCREVAI_COMPUTE_TYPE=int8

# Diarização (fine-tuning)
TRANSCREVAI_DIARIZATION_THRESHOLD=0.335
TRANSCREVAI_DIARIZATION_MIN_CLUSTER_SIZE=12
TRANSCREVAI_DIARIZATION_MIN_SPEAKERS=
TRANSCREVAI_DIARIZATION_MAX_SPEAKERS=

# Performance
TRANSCREVAI_MAX_MEMORY=2.0
TRANSCREVAI_LOG_LEVEL=INFO
```

---

## Requisitos de Sistema

### Mínimo (funcionamento básico)
- **OS:** Windows 10/11 (64-bit), Linux, macOS
- **CPU:** 4+ cores (qualquer processador x86-64 moderno)
- **RAM:** 8GB (aplicação usa ~2GB em pico)
- **Storage:** 25GB disponível (imagem Docker com modelos embedded)
- **Network:** Apenas para download inicial da imagem Docker

### Recomendado (melhor performance)
- **CPU:** 8+ cores
- **RAM:** 16GB
- **Storage:** SSD

**Nota:** A aplicação é CPU-only. Não depende de GPU para processamento.

---

## API Endpoints

### HTTP Endpoints

- **GET** `/` - Interface web principal
- **GET** `/health` - Health check endpoint
- **POST** `/upload` - Upload de arquivo de áudio (max 100MB, 10min)
- **GET** `/download-srt/{session_id}` - Download de arquivo SRT
- **GET** `/api/download/{session_id}/{file_type}` - Download genérico (audio/transcript/subtitles)

### WebSocket Endpoint

- **WS** `/ws/{session_id}` - Conexão para gravação ao vivo

**Rate Limiting:**
- HTTP endpoints: 10 requests/minuto por IP
- WebSocket: 20 conexões/minuto por IP

---
---

# TranscrevAI (English)

## Overview

TranscrevAI is a high-performance application for audio transcription and speaker diarization. It takes an audio input and provides a complete transcription, identifying who said what and when. It is designed to be a powerful tool for anyone who needs fast and accurate transcriptions of conversations, meetings, or recordings.

All transcription occurs locally on the machine where the server is running, without the use of any external APIs, ensuring data privacy. This offline architecture strongly aligns with the security and data minimization principles of the Brazilian General Data Protection Law (LGPD).

## Features

- **High-Performance Transcription:** Uses the faster-whisper model for fast, local transcription (CPU-optimized implementation of OpenAI's Whisper)
- **Speaker Diarization:** Identifies different speakers in the audio using pyannote.audio with word-level alignment algorithm
- **Live Recording:** Allows audio recording directly in the browser, with disk buffering to support long recordings without consuming excess RAM
- **File Upload:** Supports uploading pre-recorded audio files
- **SRT Subtitle Generation:** Creates subtitle files for videos
- **MP4 Video Generation:** Produces videos with embedded subtitles over a black background
- **Real-time Progress Updates:** WebSocket interface with user progress monitoring

## Tech Stack

- **Backend:** Python 3.11, FastAPI
- **AI/ML Models:**
    - **Transcription:** faster-whisper (Whisper medium optimized for CPU)
    - **Diarization:** pyannote.audio 3.1
- **Core ML Library:** PyTorch (CPU-only, INT8 quantization)
- **Real-time Communication:** WebSockets
- **Audio/Video Processing:** FFmpeg, librosa
- **Deployment:** Docker, Gunicorn/Uvicorn
- **SSL/HTTPS:** Cloudflare Tunnel + automatic certificate

## Architecture

The application is built on FastAPI and follows a modern Dependency Injection (DI) based architecture, ensuring that components are modular, stable, and efficiently managed.

- **Modular Services:** Each core functionality is encapsulated in a service (TranscriptionService, PyannoteDiarizer, LiveAudioProcessor, SessionManager)
- **Session Management:** Complete lifecycle of each user session with automatic cleanup (24h timeout)
- **Asynchronous Processing:** Heavy tasks executed in separate worker threads to avoid blocking the main server
- **Disk Buffering:** Long recordings temporarily stored on disk, allowing low memory consumption
- **Adaptive Optimization:** Automatic hardware detection (CPU cores, RAM) and dynamic thread allocation

## Performance

**Achieved metrics:**
- **Startup time:** <30s with model pre-loading
- **Memory usage:** ~2GB peak (optimized for 8GB RAM systems)
- **Processing ratio:** ~1.5x realtime
- **Accuracy PT-BR:** 90%+ with post-processing linguistic corrections
- **Architecture:** CPU-only with INT8 quantization for universal compatibility

---

## Installation and Usage

### Online Demo

**Access: https://transcrevai.online**

Test TranscrevAI directly in your browser without installing anything.

**Features:**
- Automatic HTTPS via Cloudflare
- All features available (transcription, diarization, live recording)
- Ideal for quick system evaluation

**Note:** This is a demonstration instance running on dedicated hardware. For production or development use, install locally.

---

## Option 1 — Docker (Recommended for Testers and Recruiters)

The simplest way to run TranscrevAI. No Python, FFmpeg or Hugging Face token required.

**Prerequisites:** Docker Desktop installed and running. ~25GB disk space.

### Without cloning the repository

```bash
curl -L https://raw.githubusercontent.com/hiperim/transcrevai/main/docker-compose.pull.yml -o docker-compose.yml
docker compose up
```

### With the repository cloned

```bash
git clone https://github.com/hiperim/transcrevai.git
cd transcrevai
docker compose -f docker-compose.pull.yml up
```

### Access

```
http://localhost:8000
```

The image (~20GB with embedded ML models) is automatically downloaded from Docker Hub on first run. Subsequent runs start instantly.

### Useful commands

```bash
# Run in background
docker compose -f docker-compose.pull.yml up -d

# View logs
docker compose -f docker-compose.pull.yml logs -f

# Stop
docker compose -f docker-compose.pull.yml down
```

---

## Option 2 — Local Installation (For Development)

**Requires Python 3.11+, FFmpeg and Hugging Face token.**

1. Clone repository:
   ```bash
   git clone https://github.com/hiperim/transcrevai.git
   cd transcrevai
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv venv

   # Windows
   .\venv\Scripts\activate

   # Linux/Mac
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   # Production
   pip install -r requirements.txt

   # Development (includes pytest)
   pip install -r requirements-dev.txt
   ```

4. Configure token in `.env`:
   ```bash
   HUGGING_FACE_HUB_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```

5. Download AI/ML models:
   ```bash
   python Certification_SSL_ModelsCache/download_models.py
   ```

   This downloads (~3-5GB):
   - faster-whisper-medium (transcription)
   - pyannote/speaker-diarization-3.1
   - pyannote/segmentation-3.0
   - pyannote/wespeaker embeddings

6. Run application:
   ```bash
   python main.py
   ```

7. Access: `http://localhost:8000`

---

## Local HTTPS Configuration (Optional)

This section is relevant **only** if you want to run the app locally with HTTPS (`https://localhost`). For normal use via `http://localhost:8000` this is not needed.

Run the automated script:
```batch
# Windows (as Administrator)
.\Certification_SSL_ModelsCache\setup_dev_certs.bat
```

This script installs mkcert and generates trusted local certificates for `https://localhost:8000`.

**Complete documentation:** [SSL_SETUP.md](./Certification_SSL_ModelsCache/SSL_SETUP.md)

---

## Tests

The application includes a complete test suite:

```bash
# All tests
pytest

# Specific tests
pytest tests/test_services.py
pytest tests/test_accuracy_performance.py
pytest tests/test_live_server.py

# With coverage
pytest --cov=src tests/
```

**Tests include:**
- Unit tests with mocks
- Integration tests with real server
- Quality metrics (WER/CER)
- Memory usage monitoring

---

## Technical Documentation

- **[DOCKER_DEPLOYMENT.md](./SETUP_Docker_Models_Local-install/DOCKER_DEPLOYMENT.md)** - Complete Docker deployment guide
- **[SSL_SETUP.md](./Certification_SSL_ModelsCache/SSL_SETUP.md)** - HTTPS configuration for development
- **[pipeline_workflow.md](./pipeline_workflow.md)** - Detailed processing flow diagram

---

## Project Structure

```
transcrevai/
├── src/                                    # Main source code
│   ├── transcription.py                    # Transcription service (faster-whisper)
│   ├── diarization.py                      # Diarization service (pyannote)
│   ├── audio_processing.py                 # Audio processing and sessions
│   ├── pipeline.py                         # Complete pipeline orchestration
│   ├── dependencies.py                     # Dependency injection
│   ├── exceptions.py                       # Custom exception hierarchy
│   ├── file_manager.py                     # File and storage management
│   └── websocket_handler.py                # WebSocket validation
├── tests/                                  # Test suite
│   ├── test_services.py                    # Unit tests
│   ├── test_accuracy_performance.py        # Accuracy and performance tests
│   ├── test_live_server.py                 # Integration tests
│   ├── metrics.py                          # WER/CER calculations
│   ├── utils.py                            # Test utilities
│   └── conftest.py                         # Pytest fixtures
├── config/                                 # Application configuration
│   └── app_config.py                       # AppConfig with validation
├── static/                                 # Frontend (JavaScript, CSS)
├── templates/                              # HTML templates (Jinja2)
├── Certification_SSL_ModelsCache/          # SSL and model cache
│   ├── download_models.py                  # Automatic model download
│   ├── setup_dev_certs.bat                 # SSL setup for development
│   └── SSL_SETUP.md                        # SSL configuration guide
├── SETUP_Docker_Models_Local-install/      # Docker build scripts
│   ├── build-multiarch.ps1                 # Multi-arch Docker build (Windows)
│   ├── build-multiarch.sh                  # Multi-arch Docker build (Linux/Mac)
│   └── DOCKER_DEPLOYMENT.md               # Docker deployment guide
├── Dockerfile.multiarch                    # Multi-arch Docker image (AMD64+ARM64)
├── docker-compose.yml                      # Local build (requires HF token)
├── docker-compose.pull.yml                 # Pull from Docker Hub (no token needed)
├── pytest.ini                              # Pytest configuration
├── pyrightconfig.json                      # Type checking
└── main.py                                 # Application entry point
```

---

## Configuration via Environment Variables

```bash
# Server
TRANSCREVAI_HOST=0.0.0.0
TRANSCREVAI_PORT=8000

# SSL (optional - local development)
TRANSCREVAI_SSL_CERT=certs/localhost.pem
TRANSCREVAI_SSL_KEY=certs/localhost-key.pem

# Model
TRANSCREVAI_MODEL_NAME=medium
TRANSCREVAI_DEVICE=cpu
TRANSCREVAI_COMPUTE_TYPE=int8

# Diarization (fine-tuning)
TRANSCREVAI_DIARIZATION_THRESHOLD=0.335
TRANSCREVAI_DIARIZATION_MIN_CLUSTER_SIZE=12
TRANSCREVAI_DIARIZATION_MIN_SPEAKERS=
TRANSCREVAI_DIARIZATION_MAX_SPEAKERS=

# Performance
TRANSCREVAI_MAX_MEMORY=2.0
TRANSCREVAI_LOG_LEVEL=INFO
```

---

## System Requirements

### Minimum (basic functionality)
- **OS:** Windows 10/11 (64-bit), Linux, macOS
- **CPU:** 4+ cores (any modern x86-64 processor)
- **RAM:** 8GB (application uses ~2GB at peak)
- **Storage:** 25GB available (Docker image with embedded models)
- **Network:** Only for initial Docker image download

### Recommended (better performance)
- **CPU:** 8+ cores
- **RAM:** 16GB
- **Storage:** SSD

**Note:** The application is 100% CPU-only. No GPU required.

---

## API Endpoints

### HTTP Endpoints

- **GET** `/` - Main web interface
- **GET** `/health` - Health check endpoint
- **POST** `/upload` - Upload audio file (max 100MB, 10min)
- **GET** `/download-srt/{session_id}` - Download SRT file
- **GET** `/api/download/{session_id}/{file_type}` - Generic download (audio/transcript/subtitles)

### WebSocket Endpoint

- **WS** `/ws/{session_id}` - Connection for live recording

**Rate Limiting:**
- HTTP endpoints: 10 requests/minute per IP
- WebSocket: 20 connections/minute per IP
