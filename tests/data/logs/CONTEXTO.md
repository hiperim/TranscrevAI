# Contexto — Branch diarizacao-2

## Objetivo
Melhorar diarização do app. Problema raiz: pyannote 3.1 não detecta speakers corretamente em áudios curtos.

## O que já foi tentado (e falhou)
- WhisperX (b2cea13) — não melhorou, raiz não era timestamp delta
- Pitch-matching (revertido em 911e82a) — piorava resultado
- Pré-processamento de áudio — sem ganho
- margin=1.0s — melhor resultado até agora, mantido

## Planos ja testados (branch diarizacao-2)
Testar em sequência, benchmarkando antes e depois de cada mudança:

1. `min_cluster_size` 12 → 6 — permite clusters pequenos (speakers que falam pouco)
2. `min_duration_on=0.1`, `min_duration_off=0.0` — detecta trocas de voz rápidas
3. Avaliar SpeechBrain se acima não resolver (já instalado: speechbrain==1.0.3)

## Arquivos relevantes
- `src/diarization.py` — pipeline pyannote, align_speakers_by_word(), double-remapping (linhas 144-146 e 221-222)
- `src/subtitle_generator.py` — trunca texto em 2 linhas (linha 147) — bug secundário a corrigir
- `config/app_config.py` — diarization_threshold=0.335, min_cluster_size=12, min/max_speakers=None
- `tests/benchmark_diarizacao.py` — script de benchmark criado nesta branch
- `tests/metrics.py` — WER/CER já implementados

## Arquivos de teste
- Áudio: `tests/data/recordings/teste_live_1.wav`
- Referência correta: `tests/data/recordings/expected_results_teste_live_1.srt`
- Logs de benchmark: `tests/data/logs/benchmark_*.json`

## Como rodar benchmark
```bash
cd C:\TranscrevAI
venv\Scripts\activate
python tests/benchmark_diarizacao.py
```

## Métricas do benchmark
- WER normalizado (transcrição)
- Acurácia de speaker % (diarização)
- Speakers esperados vs. detectados
- Speed ratio

## Venv ativo
`venv` (não venv_community1)
