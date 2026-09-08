"""Explicit one-time model download. Never imported by the running application."""
import hashlib
import urllib.request
from uuid import uuid4
from .offline_tts import MODEL_DIR

# Immutable upstream revision; ONNX SHA-256 values are published LFS hashes.
REVISION = '1162a9173d0ce503555aed757976b7a9912eae4c'
BASE = f'https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/en/en_GB'
MODELS = {
    'northern_english_male': '57a219ae8e638873db7d18893304be5069c42868f392bb95c3ff17f0690d0689',
    'jenny_dioco': '469c630d209e139dd392a66bf4abde4ab86390a0269c1e47b4e5d7ce81526b01',
}
CONFIG_HASHES = {
    'northern_english_male': '69557ed3d974463453e9b0c09dd99a7ed0e52b8b87b64b357dbeeb2540a97d47',
    'jenny_dioco': 'a9a7a93a317c9a3cb6563e37eb057df9ef09c06188a8a4341b0fcb58cba54dd4',
}

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def download(url, target, expected=None):
    if target.exists() and (digest(target) == expected if expected else target.stat().st_size > 0):
        print(f'Already installed: {target.name}', flush=True)
        return
    temporary = target.with_name(target.name + '.' + uuid4().hex + '.part')
    print(f'Downloading {target.name}...', flush=True)
    try:
        with urllib.request.urlopen(url, timeout=90) as source, temporary.open('wb') as output:
            while chunk := source.read(1024*1024):
                output.write(chunk)
        if expected and digest(temporary) != expected:
            raise RuntimeError(f'Download checksum mismatch: {target.name}. Retry setup.')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)

def main():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for voice, checksum in MODELS.items():
        name = f'en_GB-{voice}-medium'
        url = f'{BASE}/{voice}/medium'
        download(f'{url}/{name}.onnx', MODEL_DIR / f'{name}.onnx', checksum)
        download(f'{url}/{name}.onnx.json', MODEL_DIR / f'{name}.onnx.json', CONFIG_HASHES[voice])
        download(f'{url}/MODEL_CARD', MODEL_DIR / f'{name}.MODEL_CARD')
    print('Both offline voices are installed. Narration no longer needs internet.', flush=True)

if __name__ == '__main__':
    main()
