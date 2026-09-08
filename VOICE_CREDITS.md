# Offline voice credits

JD Training Studio uses [Piper](https://github.com/OHF-Voice/piper1-gpl), a local neural speech engine. Piper is distributed under GPL-3.0; its installation includes its license. Voice models are downloaded separately and are not committed to this repository.

The one-time downloader pins model repository revision `1162a9173d0ce503555aed757976b7a9912eae4c` and verifies SHA-256 checksums for model and configuration files. Each downloaded voice includes its upstream model card under `models/piper/`.

## Northern English male

- Model: [en_GB-northern_english_male-medium](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_GB/northern_english_male/medium)
- Dataset: [OpenSLR 83](https://www.openslr.org/83/)
- The upstream model card identifies the dataset license as [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

## Jenny (Dioco)

- Model: [en_GB-jenny_dioco-medium](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_GB/jenny_dioco/medium)
- Voice recorded by Jenny, with an Irish accent; the Piper model uses the en_GB locale.
- Dataset and terms: [Dioco Jenny TTS dataset](https://github.com/dioco-group/jenny-tts-dataset)
- The dataset permits commercial use and requires the name Jenny, preferably Jenny (Dioco), in interfaces generating speech. The app displays that attribution in its voice selector.

Piper API reference: [Python synthesis API](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md).
