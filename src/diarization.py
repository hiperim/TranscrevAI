"""
Project's Hugging Face cache for local diarization pipeline - run file "'projectRootFolder'/setup_certs_SSL_ModelsCache/download_models.py"
"""

import os
from pathlib import Path
import asyncio
import logging
from typing import Dict, Any, List, Optional

# Set HF_HOME before importing pyannote.audio or torch - forces the library to use local embedded cache directory
# Use HF_HOME if already set (e.g., in Docker), otherwise use project-local cache
if 'HF_HOME' in os.environ:
    MODELS_CACHE_DIR = Path(os.environ['HF_HOME'])
else:
    MODELS_CACHE_DIR = Path(__file__).parent.parent / "models" / ".cache"
    os.environ['HF_HOME'] = str(MODELS_CACHE_DIR)


import torch
from pyannote.audio import Pipeline
from dotenv import load_dotenv
import librosa
import numpy as np
from config.app_config import get_config
from src.executor import ml_executor

logger = logging.getLogger(__name__)
load_dotenv()
config = get_config()


class PyannoteDiarizer:
    def __init__(self, device: str = "cpu", embedding_batch_size: int = 8):
        logger.info(f"Initializing pyannote.audio pipeline from local cache: {MODELS_CACHE_DIR}")
        self.device = device
        self.embedding_batch_size = embedding_batch_size
        self.pipeline: Optional[Pipeline] = None

        try:
            # Load pipeline from cache (already initialized during build)
            os.environ['HF_HUB_OFFLINE'] = '1'
            os.environ['TRANSFORMERS_OFFLINE'] = '1'
            self.pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
            logger.info("Pipeline loaded from local cache.")

            # Read pipeline's optimized defaults, then override only what we need
            instantiate_params = self.pipeline.parameters(instantiated=True)
            instantiate_params["clustering"]["threshold"] = config.diarization_threshold
            instantiate_params["clustering"]["min_cluster_size"] = config.diarization_min_cluster_size

            # Add min/max speakers if specified in config
            if config.diarization_min_speakers is not None:
                instantiate_params["clustering"]["min_clusters"] = config.diarization_min_speakers
            if config.diarization_max_speakers is not None:
                instantiate_params["clustering"]["max_clusters"] = config.diarization_max_speakers

            self.pipeline.instantiate(instantiate_params)
            logger.info(f"Pipeline instantiated with threshold={config.diarization_threshold}, min_cluster_size={config.diarization_min_cluster_size}")

            # Move to device and set batch size
            self.pipeline.to(torch.device(self.device))
            self.pipeline.embedding_batch_size = self.embedding_batch_size

            logger.info("Diarization pipeline initialized successfully.")

        except Exception as e:
            logger.error(f"Failed to load diarization pipeline: {e}", exc_info=True)
            self.pipeline = None

    async def diarize(self, audio_path: str, transcription_segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.pipeline:
            logger.error("Diarization pipeline not available. Falling back to single speaker diarization.")
            for seg in transcription_segments:
                seg['speaker'] = 'SPEAKER_01'
            return {"segments": transcription_segments, "num_speakers": 1}

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            ml_executor,
            self._process_diarization_sync,
            audio_path,
            transcription_segments
        )

    def _process_diarization_sync(self, audio_path: str, transcription_segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.pipeline:
            raise RuntimeError("Diarization pipeline is not initialized.")

        logger.info(f"Starting pyannote.audio diarization for: {audio_path}")
        try:
            diarization_result, centroids = self.pipeline(audio_path, return_embeddings=True)
            speaker_labels = diarization_result.labels()
            centroids_dict = {label: centroids[i] for i, label in enumerate(speaker_labels)}
            raw_segs = [(t.start, t.end, spk) for t, _, spk in diarization_result.itertracks(yield_label=True)]
            logger.info(f"RAW pyannote output: {[(s[2], round(s[0],3), round(s[1],3)) for s in raw_segs]}")
            for i in range(1, len(raw_segs)):
                gap = raw_segs[i][0] - raw_segs[i-1][1]
                logger.info(f"RAW gap {raw_segs[i-1][2]}->{raw_segs[i][2]}: {gap*1000:.0f}ms")
            diarization_result = merge_short_gap_speakers(diarization_result, centroids_dict, gap_threshold=0.35)
            num_speakers = len(diarization_result.labels())
            logger.info(f"pyannote.audio detected {num_speakers} speakers (after gap merge)")

            aligned_segments = align_speakers_by_word(transcription_segments, diarization_result, audio_path)
            result = {"segments": aligned_segments, "num_speakers": int(num_speakers)}
            return result
        except Exception as e:
            logger.error(f"Diarization with pyannote.audio failed: {e}", exc_info=True)
            for seg in transcription_segments:
                seg['speaker'] = 'SPEAKER_01'
            return {"segments": transcription_segments, "num_speakers": 1}

def merge_short_gap_speakers(diarization_result, centroids_dict: dict, gap_threshold: float = 0.35):
    """
    Funde speakers diferentes com 0 < gap < gap_threshold — pausa fluente, não troca real.
    Baseado no padrão CPQD: 300ms é o mínimo para silêncio real entre speakers.
    Usa centroides de embedding para fusão de clusters com alta similaridade de cosseno.
    """
    from pyannote.core import Annotation

    segments = [
        (turn, speaker)
        for turn, _, speaker in diarization_result.itertracks(yield_label=True)
    ]
    segments.sort(key=lambda x: x[0].start)

    if len(segments) < 2:
        return diarization_result

    # Passo 0: segment_remap — segmento curto sanduichado entre segmentos do mesmo speaker é artefato
    # Padrão: SPK_A ... SPK_B(curto) ... SPK_A → SPK_B é overlap detection espúrio
    segment_remap: dict = {}  # key: (start, end, spk) → novo label
    for i, (turn, spk) in enumerate(segments):
        seg_dur = turn.end - turn.start
        if seg_dur >= 0.35:
            continue
        prev_spk = segments[i - 1][1] if i > 0 else None
        next_spk = segments[i + 1][1] if i < len(segments) - 1 else None
        if prev_spk and prev_spk != spk and prev_spk == next_spk:
            logger.info(
                f"Segment overlap artifact: {spk} {turn.start:.3f}-{turn.end:.3f} "
                f"({seg_dur*1000:.0f}ms) sanduichado por {prev_spk} → remapeando para {prev_spk}"
            )
            segment_remap[(turn.start, turn.end, spk)] = prev_spk
        elif prev_spk and prev_spk != spk:
            gap_prev = turn.start - segments[i - 1][0].end
            if abs(gap_prev) < 0.001:
                logger.info(
                    f"Segment overlap artifact: {spk} {turn.start:.3f}-{turn.end:.3f} "
                    f"({seg_dur*1000:.0f}ms) adjacente a {prev_spk} → remapeando para {prev_spk}"
                )
                segment_remap[(turn.start, turn.end, spk)] = prev_spk

    # Passo 1: remap por label — gap fluente entre speakers diferentes
    remap: dict = {}
    for i in range(1, len(segments)):
        prev_turn, prev_spk = segments[i - 1]
        curr_turn, curr_spk = segments[i]

        resolved_prev = remap.get(prev_spk, prev_spk)
        resolved_curr = remap.get(curr_spk, curr_spk)

        if resolved_prev == resolved_curr:
            continue

        gap = curr_turn.start - prev_turn.end
        if 0 < gap < gap_threshold:
            logger.info(
                f"Gap merge: {resolved_curr} → {resolved_prev} "
                f"(gap={gap*1000:.0f}ms entre {prev_turn.end:.2f}s e {curr_turn.start:.2f}s)"
            )
            remap[curr_spk] = resolved_prev

    if not remap and not segment_remap:
        return diarization_result

    # Após Passo 0: se um label teve segmentos sanduichados remapeados E tem segmentos longos,
    # esses longos foram contaminados pelo clustering do artefato → remapear label inteiro.
    # Só aplica se TODOS os segmentos curtos do label foram identificados como artefatos
    # (sanduíche confirmado), garantindo que o label não tem fala curta legítima.
    labels_with_remap = set(k[2] for k in segment_remap)
    for label in labels_with_remap:
        label_segs = [(t, s) for t, s in segments if s == label]
        short_segs = [(t, s) for t, s in label_segs if (t.end - t.start) < 0.35]
        long_segs = [(t, s) for t, s in label_segs if (t.end - t.start) >= 0.35]
        all_short_remapped = all((t.start, t.end, s) in segment_remap for t, s in short_segs)

        if long_segs and all_short_remapped:
            # Filtro de Coerência de Turno — três gatilhos simultâneos:
            # 1. Artefato curto sanduichado (já garantido pelo Passo 0)
            # 2. Primeiro segmento longo do label suspeito começa após o fim real do dominante
            # 3. Label suspeito tem apenas 1 bloco longo (múltiplos = speaker real com turnos)
            #
            # dominant_spk = destino do artefato que aparece mais cedo no áudio
            # (artefatos adjacentes ao início têm precedência — são o "speaker original")
            short_remapped = [(t, segment_remap[(t.start, t.end, s)])
                              for t, s in short_segs if (t.start, t.end, s) in segment_remap]
            short_remapped.sort(key=lambda x: x[0].start)
            dominant_spk = short_remapped[0][1] if short_remapped else None
            if dominant_spk:
                first_long_start = min(t.start for t, _ in long_segs)
                dominant_segs_before = [t for t, s in segments
                                        if s == dominant_spk and t.end <= first_long_start]
                dominant_end = max(t.end for t in dominant_segs_before) if dominant_segs_before else 0
                long_starts_after_dominant = first_long_start >= dominant_end - 0.1
                single_long_block = len(long_segs) == 1
                if long_starts_after_dominant and single_long_block:
                    remap[label] = dominant_spk
                    logger.info(
                        f"Label remap: {label} → {dominant_spk} "
                        f"(coerência de turno: 1 bloco longo começa após fim do dominante em {dominant_end:.2f}s)"
                    )
                else:
                    logger.info(
                        f"Label remap ignorado: {label} — "
                        f"{'múltiplos blocos longos' if not single_long_block else f'longo começa em {first_long_start:.2f}s antes do dominante terminar em {dominant_end:.2f}s'}"
                    )

    # Passo 3 (desabilitado): fusão por embedding similarity + intercalação de turnos.
    # Tentativa descartada: casos de 1 speaker sequencial (audio_teste_4) e 2 speakers
    # reais sequenciais (two.speakers.wav) são estruturalmente indistinguíveis por
    # contagem de switches e similaridade de cosseno — qualquer threshold causa regressão.
    # O centroids_dict é mantido como parâmetro para uso futuro.
    _ = centroids_dict

    # Resolver remap transitivamente: A→B→C deve virar A→C
    def resolve_remap(label, visited=None):
        if visited is None:
            visited = set()
        if label in visited:
            return label  # ciclo — para aqui
        visited.add(label)
        target = remap.get(label)
        if target is None or target == label:
            return label
        return resolve_remap(target, visited)

    merged = Annotation()
    for turn, speaker in segments:  # reutiliza mesma lista — mesmos objetos Segment, keys batem
        key = (turn.start, turn.end, speaker)
        if key in segment_remap:
            # Artefato curto — vai direto para o destino do remap, depois resolve transitivamente
            intermediate = segment_remap[key]
            new_label = resolve_remap(intermediate)
        else:
            new_label = resolve_remap(speaker)
        merged[turn] = new_label

    return merged


def extract_pitch(audio_path: str, start_time: float, end_time: float) -> Optional[float]:
    """Extract mean F0 (pitch) from audio segment"""
    try:
        y, sr = librosa.load(audio_path, sr=16000, offset=start_time, duration=end_time-start_time)
        if len(y) == 0:
            return None
        f0 = librosa.yin(y, fmin=50, fmax=400, sr=sr)
        f0_valid = f0[f0 > 0]
        return float(np.median(f0_valid)) if len(f0_valid) > 0 else None
    except Exception as e:
        logger.debug(f"Pitch extraction failed: {e}")
        return None

def align_speakers_by_word(transcription_segments: List[Dict[str, Any]], diarization_result, audio_path: Optional[str] = None) -> List[Dict[str, Any]]:
    logger.info("Aligning speakers to transcription segments...")
    if not diarization_result:
        logger.warning("Diarization result is None/empty, assigning SPEAKER_01 to all")
        for segment in transcription_segments:
            segment['speaker'] = 'SPEAKER_01'
        return transcription_segments

    diarization_segments = []
    speakers_found = set()
    speaker_first_appearance = {}  # Track first timestamp for each speaker

    for turn, _, speaker in diarization_result.itertracks(yield_label=True):
        diarization_segments.append({
            'start': turn.start,
            'end': turn.end,
            'speaker': speaker
        })
        speakers_found.add(speaker)

        # Track first appearance time
        if speaker not in speaker_first_appearance:
            speaker_first_appearance[speaker] = turn.start

    logger.info(f"Diarization found {len(speakers_found)} unique speakers: {sorted(speakers_found)}")

    # Sort speakers by first appearance time (chronological order)
    sorted_speakers = sorted(speakers_found, key=lambda spk: speaker_first_appearance[spk])
    speaker_mapping = {old: f"SPEAKER_{str(i+1).zfill(2)}" for i, old in enumerate(sorted_speakers)}
    logger.info(f"Speaker mapping (chronological order): {speaker_mapping}")

    def find_speaker_at_timestamp(timestamp: float, margin: float = 0.0) -> Optional[str]:
        """Find speaker at timestamp, prioritizing closest segment center when overlapping"""
        candidates = []
        for seg in diarization_segments:
            if seg['start'] <= timestamp + margin and seg['end'] >= timestamp - margin:
                # Calculate distance from timestamp to segment center
                seg_center = (seg['start'] + seg['end']) / 2
                distance_to_center = abs(timestamp - seg_center)
                candidates.append((seg['speaker'], distance_to_center))

        if candidates:
            # Return speaker with closest center (smallest distance)
            return min(candidates, key=lambda x: x[1])[0]
        return None

    for segment in transcription_segments:
        if 'words' not in segment or not segment['words']:
            # Fallback: use segment midpoint if no word timestamps
            mid_timestamp = (segment['start'] + segment['end']) / 2
            speaker = find_speaker_at_timestamp(mid_timestamp, margin=1.0)
            if speaker:
                segment['speaker'] = speaker_mapping.get(speaker, speaker)
            else:
                segment['speaker'] = 'SPEAKER_XX'
            continue

        # Use word-level timestamps for precise alignment
        # Margin of 1.0s to compensate for VAD temporal desynchronization
        word_speaker_counts: Dict[str, int] = {}
        for word in segment['words']:
            word_mid = (word['start'] + word['end']) / 2
            speaker = find_speaker_at_timestamp(word_mid, margin=1.0)

            if speaker:
                word['speaker'] = speaker_mapping.get(speaker, speaker)
                word_speaker_counts[speaker] = word_speaker_counts.get(speaker, 0) + 1
            else:
                word['speaker'] = 'SPEAKER_XX'

        logger.info(f"Segment {segment['start']:.2f}-{segment['end']:.2f}s votes: {word_speaker_counts}")

        if word_speaker_counts:
            dominant_speaker_original = max(word_speaker_counts, key=lambda spk: word_speaker_counts[spk])
            segment['speaker'] = speaker_mapping.get(dominant_speaker_original, dominant_speaker_original)
        else:
            segment['speaker'] = 'SPEAKER_XX'

    # Log which speakers were actually assigned to segments
    assigned_speakers_original = set()
    for seg in transcription_segments:
        mapped_speaker = seg.get('speaker', 'UNKNOWN')
        # Reverse lookup to get original speaker
        for orig, mapped in speaker_mapping.items():
            if mapped == mapped_speaker:
                assigned_speakers_original.add(orig)
                break

    assigned_speakers = set(seg.get('speaker', 'UNKNOWN') for seg in transcription_segments)
    logger.info(f"Speakers assigned to transcription segments: {sorted(assigned_speakers)}")

    # Re-map speakers by first TRANSCRIPTION segment appearance (not diarization)
    speaker_first_transcription = {}
    for seg in transcription_segments:
        spk = seg.get('speaker')
        if spk and spk not in ['SPEAKER_XX'] and spk not in speaker_first_transcription:
            speaker_first_transcription[spk] = seg['start']

    # Re-number based on transcription order
    sorted_by_transcription = sorted(speaker_first_transcription.keys(), key=lambda s: speaker_first_transcription[s])
    final_mapping = {old: f"SPEAKER_{str(i+1).zfill(2)}" for i, old in enumerate(sorted_by_transcription)}

    # Apply final mapping to all segments and words
    for seg in transcription_segments:
        if seg.get('speaker') in final_mapping:
            seg['speaker'] = final_mapping[seg['speaker']]
        # Also update word-level speakers
        if 'words' in seg:
            for word in seg['words']:
                if word.get('speaker') in final_mapping:
                    word['speaker'] = final_mapping[word['speaker']]

    logger.info(f"Final speaker mapping by transcription order: {final_mapping}")

    # Find speakers detected by pyannote but not assigned to any transcription segment
    unassigned_speakers = speakers_found - assigned_speakers_original

    if unassigned_speakers and audio_path:
        logger.info(f"Found {len(unassigned_speakers)} unassigned speakers: {sorted(unassigned_speakers)}")
        logger.info("Attempting pitch-based re-attribution")

        # Extract pitch for assigned speakers
        speaker_pitches = {}
        for seg in transcription_segments:
            if seg.get('speaker') and seg['speaker'] != 'SPEAKER_XX':
                pitch = extract_pitch(audio_path, seg['start'], seg['end'])
                if pitch:
                    if seg['speaker'] not in speaker_pitches:
                        speaker_pitches[seg['speaker']] = []
                    speaker_pitches[seg['speaker']].append(pitch)

        # Calculate median pitch per speaker
        speaker_median_pitch = {spk: np.median(pitches) for spk, pitches in speaker_pitches.items() if len(pitches) > 0}
        logger.info(f"Speaker pitches: {speaker_median_pitch}")

        for speaker in sorted(unassigned_speakers):
            speaker_segments = [seg for seg in diarization_segments if seg['speaker'] == speaker]
            for dia_seg in speaker_segments:
                # Try pitch matching
                pitch = extract_pitch(audio_path, dia_seg['start'], dia_seg['end'])
                best_match = None

                if pitch and speaker_median_pitch:
                    min_diff = float('inf')
                    for spk, med_pitch in speaker_median_pitch.items():
                        diff = abs(pitch - med_pitch)
                        if diff < min_diff:
                            min_diff = diff
                            best_match = spk

                    # Only re-attribute if difference is reasonable (< 50 Hz)
                    if min_diff < 50:
                        logger.info(f"  Pitch match: {speaker_mapping.get(speaker, speaker)} → {best_match} (diff: {min_diff:.1f}Hz)")
                        # Find and update existing segment or add
                        for seg in transcription_segments:
                            if abs(seg['start'] - dia_seg['start']) < 0.5 and seg.get('speaker') == best_match:
                                logger.info(f"  Merged into existing {best_match} segment")
                                break
                        else:
                            mapped_spk = speaker_mapping.get(speaker, speaker)
                            final_spk = final_mapping.get(mapped_spk, mapped_spk)
                            synthetic_segment = {
                                'start': dia_seg['start'],
                                'end': dia_seg['end'],
                                'text': '[inaudível]',
                                'speaker': final_spk,
                                'avg_logprob': -1.0,
                                'words': []
                            }
                            transcription_segments.append(synthetic_segment)
                        continue

                # Fallback: add as [inaudível] with final mapping
                mapped_spk = speaker_mapping.get(speaker, speaker)
                final_spk = final_mapping.get(mapped_spk, mapped_spk)
                synthetic_segment = {
                    'start': dia_seg['start'],
                    'end': dia_seg['end'],
                    'text': '[inaudível]',
                    'speaker': final_spk,
                    'avg_logprob': -1.0,
                    'words': []
                }
                transcription_segments.append(synthetic_segment)
                logger.info(f"  Added [inaudível] for {final_spk} at {dia_seg['start']:.2f}-{dia_seg['end']:.2f}s")

        # Sort segments by start time
        transcription_segments.sort(key=lambda x: x['start'])

    elif unassigned_speakers:
        logger.info(f"Found {len(unassigned_speakers)} unassigned speakers but no audio_path for pitch tracking")
        for speaker in sorted(unassigned_speakers):
            speaker_segments = [seg for seg in diarization_segments if seg['speaker'] == speaker]
            for dia_seg in speaker_segments:
                mapped_spk = speaker_mapping.get(speaker, speaker)
                final_spk = final_mapping.get(mapped_spk, mapped_spk)
                synthetic_segment = {
                    'start': dia_seg['start'],
                    'end': dia_seg['end'],
                    'text': '[inaudível]',
                    'speaker': final_spk,
                    'avg_logprob': -1.0,
                    'words': []
                }
                transcription_segments.append(synthetic_segment)
        transcription_segments.sort(key=lambda x: x['start'])

    logger.info("Speaker alignment completed successfully")
    return transcription_segments