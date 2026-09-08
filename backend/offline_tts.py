"""Local Piper narration. Runtime never downloads models or contacts a service."""
from functools import lru_cache
from importlib.util import find_spec
import json
import logging
import os
from pathlib import Path
import threading
import wave

log = logging.getLogger('jd-studio')
PREFIX = 'piper:'
MODEL_DIR = Path(os.environ.get('JD_VOICES_DIR', Path(__file__).resolve().parent.parent / 'models' / 'piper')).resolve()
VOICES = {
    'piper:en_GB-northern_english_male-medium': 'Northern English · British male',
    'piper:en_GB-jenny_dioco-medium': 'Jenny (Dioco) · English female, Irish accent',
}
DEFAULT_VOICE = next(iter(VOICES))
INSTRUCTIONS = ('Run setup-offline.bat once while connected to the internet to install '
                'Piper and download the two English voices (about 127 MB of voice files). '
                'After setup, narration works offline. Then click Refresh voices.')
_synthesis_lock = threading.Lock()

class OfflineSpeechError(ValueError):
    """A short, user-facing local speech error."""

def is_offline(voice):
    return voice.startswith(PREFIX)

def model_path(voice):
    if voice not in VOICES:
        raise OfflineSpeechError('The selected offline voice is not installed. Choose an available Piper voice. ' + INSTRUCTIONS)
    return MODEL_DIR / (voice[len(PREFIX):] + '.onnx')

@lru_cache(maxsize=1)
def status():
    choices = {}
    if find_spec('piper') is None:
        return {'ready': False, 'voices': {}, 'default_voice': DEFAULT_VOICE,
                'message': 'The offline speech engine is not installed. ' + INSTRUCTIONS}
    for voice, label in VOICES.items():
        path = model_path(voice)
        try:
            config = json.loads(path.with_suffix('.onnx.json').read_text(encoding='utf-8'))
            if path.stat().st_size > 1_000_000 and config['audio']['sample_rate'] > 0:
                choices[voice] = label
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return {'ready': bool(choices), 'voices': choices,
            'default_voice': next(iter(choices), DEFAULT_VOICE),
            'message': '' if choices else 'Offline voice files are missing or incomplete. ' + INSTRUCTIONS}

def refresh():
    status.cache_clear()
    with _synthesis_lock:
        _load_voice.cache_clear()
    return status()

def default_voice():
    return status()['default_voice']

@lru_cache(maxsize=1)
def _load_voice(voice):
    from piper import PiperVoice
    return PiperVoice.load(str(model_path(voice)), use_cuda=False)

def synthesize(text, voice, output):
    if voice not in status()['voices']:
        raise OfflineSpeechError('The selected offline voice is not installed. Refresh voices and choose an available voice. ' + INSTRUCTIONS)
    try:
        # Serialize shared phonemizer/model access and bound model memory.
        with _synthesis_lock:
            engine = _load_voice(voice)
            with wave.open(str(output), 'wb') as wav_file:
                engine.synthesize_wav(text, wav_file)
        if not output.is_file() or output.stat().st_size <= 44:
            raise RuntimeError('Empty speech audio')
    except Exception as error:
        log.exception('Piper offline synthesis failed')
        raise OfflineSpeechError('Offline speech could not be generated. Run setup-offline.bat to repair the engine/voice files, then refresh voices and retry. Details are in logs/studio.log.') from error
