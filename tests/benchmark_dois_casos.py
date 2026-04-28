"""
Benchmark de diarização — suite completa:
  1. audio_teste_2.wav     — 1 speaker, ambiente controlado
  2. audio_teste_3.wav     — 1 speaker, artefato de overlap
  3. audio_teste_4.wav     — 1 speaker, mesmo ambiente
  4. teste_live_1.wav      — 2 speakers, gravação ao vivo
  5. two.speakers.wav      — 2 speakers reais
  6. three.speakers.wav    — 3 speakers reais
  7. three.speakers_2.wav  — 3 speakers reais (variação)
  8. four.speakers.wav     — 4 speakers reais

Mede WER e acurácia de diarização. Salva log em tests/logs/.
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
from tests.metrics import calculate_dual_wer, calculate_cer, calculate_similarity, normalize_text


LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

RECORDINGS = Path(__file__).parent / "data" / "recordings"

CASES = [
    {
        "name": "single_speaker_teste2",
        "audio": RECORDINGS / "audio_teste_2.wav",
        "expected_srt": RECORDINGS / "trans_teste_2.srt",
        "expected_speakers": 1,
        "description": "1 speaker, ambiente controlado, fala contínua",
    },
    {
        "name": "single_speaker_teste3",
        "audio": RECORDINGS / "audio_teste_3.wav",
        "expected_srt": RECORDINGS / "trans_teste_3.srt",
        "expected_speakers": 1,
        "description": "1 speaker, artefato de overlap",
    },
    {
        "name": "single_speaker_teste4",
        "audio": RECORDINGS / "audio_teste_4.wav",
        "expected_srt": RECORDINGS / "trans_teste_4.srt",
        "expected_speakers": 1,
        "description": "1 speaker, mesmo ambiente, mesmo texto",
    },
    {
        "name": "live_two_speakers",
        "audio": RECORDINGS / "teste_live_1.wav",
        "expected_srt": RECORDINGS / "expected_results_teste_live_1.srt",
        "expected_speakers": 2,
        "description": "2 speakers, gravação ao vivo",
    },
    {
        "name": "two_speakers",
        "audio": RECORDINGS / "two.speakers.wav",
        "expected_txt": RECORDINGS / "expected_results_two.speakers.txt",
        "expected_speakers": 2,
        "description": "2 speakers reais, diálogo curto",
    },
    {
        "name": "three_speakers",
        "audio": RECORDINGS / "three.speakers.wav",
        "expected_txt": RECORDINGS / "expected_results_three.speakers.txt",
        "expected_speakers": 3,
        "description": "3 speakers reais, diálogo curto",
    },
    {
        "name": "three_speakers_2",
        "audio": RECORDINGS / "three.speakers_2.wav",
        "expected_txt": RECORDINGS / "expected_results_three.speakers_2.txt",
        "expected_speakers": 3,
        "description": "3 speakers reais, variação",
    },
    {
        "name": "four_speakers",
        "audio": RECORDINGS / "four.speakers.wav",
        "expected_txt": RECORDINGS / "expected_results_four.speakers.txt",
        "expected_speakers": 4,
        "description": "4 speakers reais",
    },
]


def get_git_info():
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
        dirty = subprocess.call(["git", "diff", "--quiet"], stderr=subprocess.DEVNULL) != 0
        return {"commit": commit, "branch": branch, "uncommitted_changes": dirty}
    except Exception:
        return {"commit": "unknown", "branch": "unknown", "uncommitted_changes": None}


def get_diarization_params():
    try:
        from config.app_config import get_config
        cfg = get_config()
        return {
            "diarization_threshold": cfg.diarization_threshold,
            "diarization_min_cluster_size": cfg.diarization_min_cluster_size,
            "diarization_min_speakers": cfg.diarization_min_speakers,
            "diarization_max_speakers": cfg.diarization_max_speakers,
        }
    except Exception:
        return {}


# ---------- parsers ----------------------------------------------------------

def parse_srt(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\n\n+", text.strip())
    segments = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        m = re.match(r"(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)", lines[1])
        if not m:
            continue
        def to_sec(t):
            h, mn, s = t.split(":")
            s, ms = s.split(",")
            return int(h)*3600 + int(mn)*60 + int(s) + int(ms)/1000
        content = " ".join(lines[2:])
        sp = re.match(r"\[(SPEAKER_\w+)\]\s*(.*)", content, re.DOTALL)
        speaker = sp.group(1) if sp else "UNKNOWN"
        text_only = sp.group(2).strip() if sp else content.strip()
        segments.append({
            "start": to_sec(m.group(1)),
            "end": to_sec(m.group(2)),
            "speaker": speaker,
            "text": text_only,
        })
    return segments


def parse_txt_reference(path: Path):
    """Parse expected_results txt files (Speaker_N (HH:MM-HH:MM): 'text')."""
    text = path.read_text(encoding="utf-8-sig")
    segments = []
    for line in text.splitlines():
        m = re.match(r"-?\s*(Speaker_\d+)\s*\((\d+:\d+)-(\d+:\d+)\):\s*[\"']?(.+)[\"']?", line)
        if not m:
            continue
        def mmss(t):
            parts = t.split(":")
            return int(parts[0])*60 + int(parts[1])
        segments.append({
            "start": mmss(m.group(2)),
            "end": mmss(m.group(3)),
            "speaker": m.group(1).replace("Speaker_", "SPEAKER_"),
            "text": m.group(4).strip().strip("\"'"),
        })
    return segments


def segments_to_text(segs):
    return " ".join(s["text"] for s in segs if s.get("text") and s["text"] != "[inaudível]")


# ---------- diarization accuracy --------------------------------------------

def speaker_accuracy(ref_segs, hyp_segs):
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
        "hyp_speakers": hyp_speakers,
    }


# ---------- run one case -----------------------------------------------------

async def run_case(case: dict, svc: TranscriptionService, diarizer: PyannoteDiarizer) -> dict:
    audio = case["audio"]
    print(f"\n{'='*60}")
    print(f"CASO: {case['name']}")
    print(f"Descrição: {case['description']}")
    print(f"Áudio: {audio.name}  |  Speakers esperados: {case['expected_speakers']}")
    print(f"{'='*60}")

    if not audio.exists():
        print(f"  ERRO: arquivo não encontrado: {audio}")
        return {"case": case["name"], "error": "audio file not found"}

    # Load reference
    if "expected_srt" in case:
        ref_segs = parse_srt(case["expected_srt"])
    else:
        ref_segs = parse_txt_reference(case["expected_txt"])

    ref_text = segments_to_text(ref_segs)
    print(f"Referência: {len(ref_segs)} segmentos, {len(ref_text.split())} palavras")

    # Transcription
    print("\n[1/2] Transcrevendo...")
    t0 = time.time()
    result = await svc.transcribe_with_enhancements(str(audio), word_timestamps=True)
    transcription_time = time.time() - t0
    raw_segs = result.segments if hasattr(result, "segments") else (
        result.get("segments", []) if isinstance(result, dict) else []
    )
    print(f"  Concluído em {transcription_time:.1f}s — {len(raw_segs)} segmentos")

    # Diarization
    print("\n[2/2] Diarizando...")
    t1 = time.time()
    dia_result = await diarizer.diarize(str(audio), raw_segs)
    diarization_time = time.time() - t1
    hyp_segs = dia_result.get("segments", [])
    num_speakers_detected = dia_result.get("num_speakers", 0)
    print(f"  Concluído em {diarization_time:.1f}s — {num_speakers_detected} speakers detectados")

    # Metrics
    hyp_text = segments_to_text(hyp_segs)
    wer_result = calculate_dual_wer(ref_text, hyp_text)
    cer = calculate_cer(normalize_text(ref_text), normalize_text(hyp_text))
    similarity = calculate_similarity(ref_text, hyp_text)
    sp_result = speaker_accuracy(ref_segs, hyp_segs)

    import librosa
    audio_duration = librosa.get_duration(path=str(audio))
    total_time = transcription_time + diarization_time
    speaker_count_correct = (num_speakers_detected == case["expected_speakers"])

    print(f"\n--- Resultado {case['name']} ---")
    print(f"Duração: {audio_duration:.1f}s")
    print(f"Tempo transcrição:  {transcription_time:.1f}s (ratio {transcription_time/audio_duration:.2f}x)")
    print(f"Tempo diarização:   {diarization_time:.1f}s (ratio {diarization_time/audio_duration:.2f}x)")
    print(f"Tempo total:        {total_time:.1f}s (ratio {total_time/audio_duration:.2f}x)")
    print(f"WER normalizado:    {wer_result['wer_normalized']:.4f} | Acurácia: {wer_result['accuracy_normalized_percent']:.1f}%")
    print(f"WER tradicional:    {wer_result['wer_traditional']:.4f} | Acurácia: {wer_result['accuracy_traditional_percent']:.1f}%")
    print(f"CER normalizado:    {cer:.4f} | Acurácia: {(1-cer)*100:.1f}%")
    print(f"Similaridade:       {similarity:.4f}")
    print(f"Speakers esperados: {case['expected_speakers']} | Detectados: {num_speakers_detected} | {'OK' if speaker_count_correct else 'FALHOU'}")
    print(f"Acurácia speaker:   {sp_result['accuracy_percent']}% ({sp_result['correct_segments']}/{sp_result['total_segments']} segmentos)")

    return {
        "case": case["name"],
        "description": case["description"],
        "audio_file": audio.name,
        "audio_duration_sec": round(audio_duration, 2),
        "timing": {
            "transcription_sec": round(transcription_time, 2),
            "diarization_sec": round(diarization_time, 2),
            "total_sec": round(total_time, 2),
            "transcription_ratio": round(transcription_time / audio_duration, 2),
            "diarization_ratio": round(diarization_time / audio_duration, 2),
            "total_ratio": round(total_time / audio_duration, 2),
        },
        "transcription": {
            "wer_traditional": round(wer_result["wer_traditional"], 4),
            "wer_normalized": round(wer_result["wer_normalized"], 4),
            "cer_normalized": round(cer, 4),
            "similarity": round(similarity, 4),
            "accuracy_traditional_percent": round(wer_result["accuracy_traditional_percent"], 1),
            "accuracy_normalized_percent": round(wer_result["accuracy_normalized_percent"], 1),
            "cer_accuracy_percent": round((1 - cer) * 100, 1),
        },
        "diarization": {
            "speakers_expected": case["expected_speakers"],
            "speakers_detected": num_speakers_detected,
            "speaker_count_correct": speaker_count_correct,
            "speaker_accuracy_percent": sp_result["accuracy_percent"],
            "correct_segments": sp_result["correct_segments"],
            "total_segments": sp_result["total_segments"],
            "best_label_mapping": sp_result["best_label_mapping"],
            "ref_speakers": sp_result["ref_speakers"],
            "hyp_speakers": sp_result["hyp_speakers"],
        },
        "hypothesis_segments": [
            {"start": s["start"], "end": s["end"],
             "speaker": s.get("speaker", "?"), "text": s.get("text", "")}
            for s in hyp_segs
        ],
    }


# ---------- main -------------------------------------------------------------

async def run_benchmark():
    print(f"\n{'='*60}")
    print("BENCHMARK — Suite completa de diarização (8 casos)")
    print(f"{'='*60}")

    print("\nInicializando modelos (reutilizados para todos os casos)...")
    svc = TranscriptionService(model_name="medium", device="cpu")
    await svc.initialize()
    diarizer = PyannoteDiarizer(device="cpu")

    results = []
    for case in CASES:
        r = await run_case(case, svc, diarizer)
        results.append(r)

    report = {
        "timestamp": datetime.now().isoformat(),
        "git": get_git_info(),
        "diarization_params": get_diarization_params(),
        "cases": results,
    }

    log_file = LOGS_DIR / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print("SUMÁRIO FINAL")
    print(f"{'='*60}")
    print(f"{'Caso':<30} {'Ratio':>6} {'WER':>6} {'CER':>6} {'Sim':>5} {'Acc%':>6} {'Spk':>8}")
    print("-" * 70)
    for r in results:
        if "error" in r:
            print(f"  {r['case']}: ERRO — {r['error']}")
            continue
        dia = r["diarization"]
        tr = r["transcription"]
        tm = r["timing"]
        spk_ok = "OK" if dia["speaker_count_correct"] else "FALHOU"
        print(f"{r['case']:<30} {tm['total_ratio']:>5.2f}x {tr['wer_normalized']:>6.4f} {tr['cer_normalized']:>6.4f} {tr['similarity']:>5.3f} {tr['accuracy_normalized_percent']:>5.1f}% {dia['speakers_detected']}/{dia['speakers_expected']} {spk_ok}")
    print(f"\nLog salvo em: {log_file}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
