"""
Benchmark de diarização e transcrição para teste_live_1.wav.
Mede WER (transcrição) e acurácia de speaker (diarização).
Salva resultado em tests/data/logs/.
"""

import asyncio
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

from src.transcription import TranscriptionService
from src.diarization import PyannoteDiarizer
from tests.metrics import calculate_dual_wer


def get_git_info():
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
        dirty = subprocess.call(
            ["git", "diff", "--quiet"], stderr=subprocess.DEVNULL
        ) != 0
        return {"commit": commit, "branch": branch, "uncommitted_changes": dirty}
    except Exception:
        return {"commit": "unknown", "branch": "unknown", "uncommitted_changes": None}


def get_diarization_params():
    try:
        from config.app_config import config
        return {
            "diarization_threshold": config.diarization_threshold,
            "diarization_min_cluster_size": config.diarization_min_cluster_size,
            "diarization_min_speakers": config.diarization_min_speakers,
            "diarization_max_speakers": config.diarization_max_speakers,
        }
    except Exception:
        return {}

AUDIO_PATH  = Path(__file__).parent / "data" / "recordings" / "teste_live_1.wav"
EXPECTED_SRT = Path(__file__).parent / "data" / "recordings" / "expected_results_teste_live_1.srt"
LOGS_DIR    = Path(__file__).parent / "data" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


# ---------- helpers ----------------------------------------------------------

def parse_srt(srt_path: Path):
    """Parse SRT into list of {start, end, speaker, text}."""
    text = srt_path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\n\n+", text.strip())
    segments = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        times = lines[1]
        m = re.match(r"(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)", times)
        if not m:
            continue
        def to_sec(t):
            h, mn, s = t.split(":")
            s, ms = s.split(",")
            return int(h)*3600 + int(mn)*60 + int(s) + int(ms)/1000
        content = " ".join(lines[2:])
        sp_match = re.match(r"\[(SPEAKER_\w+)\]\s*(.*)", content, re.DOTALL)
        speaker = sp_match.group(1) if sp_match else "UNKNOWN"
        text_only = sp_match.group(2).strip() if sp_match else content.strip()
        segments.append({
            "start": to_sec(m.group(1)),
            "end":   to_sec(m.group(2)),
            "speaker": speaker,
            "text": text_only
        })
    return segments


def segments_to_plain_text(segments):
    return " ".join(s["text"] for s in segments if s["text"] != "[inaudível]")


def speaker_accuracy(ref_segs, hyp_segs):
    """
    Compara speakers segmento a segmento por sobreposição temporal.
    Retorna % de segmentos com speaker correto (após melhor mapeamento de labels).
    """
    from itertools import permutations

    ref_speakers = sorted(set(s["speaker"] for s in ref_segs))
    hyp_speakers = sorted(set(s["speaker"] for s in hyp_segs))

    def overlap(a, b):
        return max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))

    def score_mapping(mapping):
        correct = 0
        for r in ref_segs:
            mapped = mapping.get(r["speaker"], r["speaker"])
            for h in hyp_segs:
                if h["speaker"] == mapped and overlap(r, h) > 0:
                    correct += 1
                    break
        return correct

    # Tenta todas as permutações de mapeamento de speakers (até 4)
    best_score = 0
    best_mapping = {}
    candidates = hyp_speakers[:len(ref_speakers)]
    if candidates:
        for perm in permutations(candidates):
            mapping = {ref_speakers[i]: perm[i] for i in range(min(len(ref_speakers), len(perm)))}
            s = score_mapping(mapping)
            if s > best_score:
                best_score = s
                best_mapping = mapping

    total = len(ref_segs)
    return {
        "correct_segments": best_score,
        "total_segments": total,
        "accuracy_percent": round(best_score / total * 100, 1) if total else 0,
        "best_label_mapping": best_mapping,
        "ref_speakers": ref_speakers,
        "hyp_speakers": hyp_speakers
    }


# ---------- main -------------------------------------------------------------

async def run_benchmark():
    print(f"\n{'='*60}")
    print(f"BENCHMARK — {AUDIO_PATH.name}")
    print(f"{'='*60}")

    if not AUDIO_PATH.exists():
        print(f"ERRO: arquivo de áudio não encontrado: {AUDIO_PATH}")
        return

    ref_segs = parse_srt(EXPECTED_SRT)
    ref_text = segments_to_plain_text(ref_segs)
    print(f"Referência: {len(ref_segs)} segmentos, {len(ref_text.split())} palavras")

    # Transcrição
    print("\n[1/2] Transcrevendo...")
    t0 = time.time()
    svc = TranscriptionService(model_name="medium", device="cpu")
    await svc.initialize()
    result = await svc.transcribe_with_enhancements(str(AUDIO_PATH), word_timestamps=True)
    transcription_time = time.time() - t0
    raw_segments = result.segments if hasattr(result, "segments") else result.get("segments", [])
    print(f"  Concluído em {transcription_time:.1f}s — {len(raw_segments)} segmentos")

    # Diarização
    print("\n[2/2] Diarizando...")
    t1 = time.time()
    diarizer = PyannoteDiarizer(device="cpu")
    dia_result = await diarizer.diarize(str(AUDIO_PATH), raw_segments)
    diarization_time = time.time() - t1
    hyp_segs = dia_result.get("segments", [])
    num_speakers_detected = dia_result.get("num_speakers", 0)
    print(f"  Concluído em {diarization_time:.1f}s — {num_speakers_detected} speakers detectados")

    # WER
    hyp_text = segments_to_plain_text(hyp_segs)
    wer_result = calculate_dual_wer(ref_text, hyp_text)

    # Acurácia de diarização
    sp_result = speaker_accuracy(ref_segs, hyp_segs)

    # Resultado
    import librosa
    audio_duration = librosa.get_duration(path=str(AUDIO_PATH))
    total_time = transcription_time + diarization_time

    report = {
        "timestamp": datetime.now().isoformat(),
        "git": get_git_info(),
        "diarization_params": get_diarization_params(),
        "audio_file": AUDIO_PATH.name,
        "audio_duration_sec": round(audio_duration, 2),
        "processing_time_sec": round(total_time, 2),
        "speed_ratio": round(total_time / audio_duration, 2),
        "transcription": {
            "wer_traditional": round(wer_result["wer_traditional"], 4),
            "wer_normalized": round(wer_result["wer_normalized"], 4),
            "accuracy_normalized_percent": round(wer_result["accuracy_normalized_percent"], 1),
        },
        "diarization": {
            "speakers_expected": len(set(s["speaker"] for s in ref_segs)),
            "speakers_detected": num_speakers_detected,
            "speaker_accuracy_percent": sp_result["accuracy_percent"],
            "correct_segments": sp_result["correct_segments"],
            "total_segments": sp_result["total_segments"],
            "best_label_mapping": sp_result["best_label_mapping"],
            "ref_speakers": sp_result["ref_speakers"],
            "hyp_speakers": sp_result["hyp_speakers"],
        },
        "hypothesis_segments": [
            {"start": s["start"], "end": s["end"],
             "speaker": s.get("speaker","?"), "text": s.get("text","")}
            for s in hyp_segs
        ]
    }

    # Salvar log
    log_file = LOGS_DIR / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Imprimir resumo
    print(f"\n{'='*60}")
    print(f"RESULTADO")
    print(f"{'='*60}")
    print(f"Duração do áudio:       {audio_duration:.1f}s")
    print(f"Tempo total:            {total_time:.1f}s (ratio: {report['speed_ratio']}x)")
    print(f"\nTranscrição:")
    print(f"  WER normalizado:      {wer_result['wer_normalized']:.4f}")
    print(f"  Acurácia:             {wer_result['accuracy_normalized_percent']:.1f}%")
    print(f"\nDiarização:")
    print(f"  Speakers esperados:   {report['diarization']['speakers_expected']}")
    print(f"  Speakers detectados:  {num_speakers_detected}")
    print(f"  Acurácia de speaker:  {sp_result['accuracy_percent']}%")
    print(f"  ({sp_result['correct_segments']}/{sp_result['total_segments']} segmentos corretos)")
    print(f"\nLog salvo em: {log_file}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
