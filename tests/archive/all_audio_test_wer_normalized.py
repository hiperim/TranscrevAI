# tests/archive/test_d_speakers.py
"""
Testa o pipeline completo com todos os arquivos de áudio de benchmark.
Mostra: transcrição, diarização, métricas (WER normalizado, speed ratio, speaker accuracy)
"""

import asyncio
import time
import sys
from pathlib import Path
import librosa

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.transcription import TranscriptionService
from src.diarization import PyannoteDiarizer
from tests.metrics import calculate_wer, calculate_wer_normalized

# ===========================================================
# CONFIGURAÇÃO
# ===========================================================

MODEL_NAME = "medium"
COMPUTE_TYPE = "int8"
DEVICE = "cpu"

# Paths
AUDIO_DIR = Path(__file__).parent.parent / "data" / "recordings"
TRUTH_DIR = Path(__file__).parent.parent / "ground_truth"

# Arquivos de teste: (audio, ground_truth, expected_speakers)
TEST_FILES = [
    ("d.speakers.wav", "d_speakers.txt", 2),
    ("q.speakers.wav", "q_speakers.txt", 4),
    ("t.speakers.wav", "t_speakers.txt", 3),
    ("t2.speakers.wav", "t2_speakers.txt", 3),
]

# ===========================================================

async def run_single_test(audio_filename, truth_filename, expected_speakers, transcription_service, diarizer):
    """Roda o pipeline para um único arquivo e retorna métricas."""

    audio_path = AUDIO_DIR / audio_filename
    truth_path = TRUTH_DIR / truth_filename

    print(f"\n{'='*60}")
    print(f"ARQUIVO: {audio_filename}")
    print(f"{'='*60}")

    if not audio_path.exists():
        print(f"❌ ERRO: Arquivo de áudio não encontrado: {audio_path}")
        return None

    if not truth_path.exists():
        print(f"❌ ERRO: Ground truth não encontrado: {truth_path}")
        return None

    expected_text = truth_path.read_text(encoding="utf-8").strip()
    audio_duration = librosa.get_duration(path=str(audio_path))
    print(f"Duração: {audio_duration:.2f}s | Speakers esperados: {expected_speakers}")

    start_time = time.time()
    try:
        transcription_result = await transcription_service.transcribe_with_enhancements(
            str(audio_path),
            whisper_params={"beam_size": 5, "best_of": 5}
        )
        diarization_result = await diarizer.diarize(
            str(audio_path),
            transcription_result.segments
        )
        end_time = time.time()
    except Exception as e:
        print(f"❌ Erro durante execução: {e}")
        import traceback
        traceback.print_exc()
        return None

    processing_time = end_time - start_time
    processing_ratio = processing_time / audio_duration
    actual_text = transcription_result.text
    detected_speakers = diarization_result["num_speakers"]

    wer = calculate_wer(expected_text, actual_text)
    wer_normalized = calculate_wer_normalized(expected_text, actual_text)
    transcription_accuracy = max(0, (1 - wer_normalized) * 100)
    diarization_accuracy = 100.0 if detected_speakers == expected_speakers else 0.0

    # Resultados
    speed_ok = processing_ratio <= 2.0
    accuracy_ok = transcription_accuracy >= 90.0
    diarization_ok = diarization_accuracy == 100.0

    print(f"\n📊 Speed Ratio: {processing_ratio:.2f}x {'✅' if speed_ok else '⚠️'}")
    print(f"📝 Accuracy normalizada: {transcription_accuracy:.2f}% (WER trad: {wer:.4f} | norm: {wer_normalized:.4f}) {'✅' if accuracy_ok else '⚠️'}")
    print(f"👥 Speakers: {detected_speakers}/{expected_speakers} {'✅' if diarization_ok else '❌'}")
    print(f"\nTexto obtido: {actual_text[:150]}{'...' if len(actual_text) > 150 else ''}")

    print("\nSegmentos:")
    for seg in diarization_result.get("segments", [])[:5]:
        print(f"   [{seg.get('speaker', '?')}] {seg.get('text', '')[:50]}...")

    return {
        "file": audio_filename,
        "speed_ratio": processing_ratio,
        "accuracy": transcription_accuracy,
        "wer": wer,
        "wer_normalized": wer_normalized,
        "detected_speakers": detected_speakers,
        "expected_speakers": expected_speakers,
        "speed_ok": speed_ok,
        "accuracy_ok": accuracy_ok,
        "diarization_ok": diarization_ok,
        "all_passed": speed_ok and accuracy_ok and diarization_ok,
    }


async def test_all_speakers():
    """Roda o pipeline completo para todos os arquivos de benchmark."""

    print("=" * 60)
    print("BENCHMARK COMPLETO - TranscrevAI")
    print(f"Modelo: {MODEL_NAME} | Compute: {COMPUTE_TYPE} | Device: {DEVICE}")
    print("=" * 60)

    print("\nInicializando serviços...")
    try:
        transcription_service = TranscriptionService(model_name=MODEL_NAME, device=DEVICE)
        await transcription_service.initialize()
        diarizer = PyannoteDiarizer()
        print("✅ Serviços inicializados")
    except Exception as e:
        print(f"❌ Erro ao inicializar: {e}")
        return

    results = []
    for audio_filename, truth_filename, expected_speakers in TEST_FILES:
        result = await run_single_test(
            audio_filename, truth_filename, expected_speakers,
            transcription_service, diarizer
        )
        if result:
            results.append(result)

    # Resumo final
    print(f"\n{'='*60}")
    print("RESUMO GERAL")
    print(f"{'='*60}")
    print(f"{'Arquivo':<20} {'Speed':>7} {'Accuracy':>10} {'Speakers':>10} {'Status':>8}")
    print("-" * 60)
    for r in results:
        status = "✅ OK" if r["all_passed"] else "⚠️  FALHOU"
        print(f"{r['file']:<20} {r['speed_ratio']:>6.2f}x {r['accuracy']:>9.1f}% {r['detected_speakers']:>4}/{r['expected_speakers']:<4} {status:>8}")

    total = len(results)
    passed = sum(1 for r in results if r["all_passed"])
    print(f"\nResultado: {passed}/{total} arquivos passaram em todos os critérios")


if __name__ == "__main__":
    asyncio.run(test_all_speakers())
