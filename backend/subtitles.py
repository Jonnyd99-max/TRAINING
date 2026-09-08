"""Deterministic phrase subtitles with estimated audio-duration timing."""
import re


def cues(scene):
    if not scene.get('subtitles_enabled') or not scene.get('audio_duration'):
        return []
    words = scene.get('narration', '').split()
    phrases, current = [], ''
    for word in words:
        # Bound exceptionally long tokens as well as ordinary phrases.
        for token in [word[i:i+42] for i in range(0, len(word), 42)]:
            if current and len(current) + len(token) + 1 > 84:
                phrases.append(current)
                current = ''
            current = (current + ' ' + token).strip()
            if re.search(r'[.!?;:]$', token) or len(current.split()) >= 12:
                phrases.append(current)
                current = ''
    if current:
        phrases.append(current)
    total = sum(len(p) for p in phrases)
    position, result = 0, []
    for phrase in phrases:
        start = position / total * scene['audio_duration']
        position += len(phrase)
        end = min(position / total * scene['audio_duration'], scene['duration'])
        if start < end:
            result.append({'start': start, 'end': end, 'text': phrase})
    return result
