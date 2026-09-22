"""Compare v0.1 buffering with v0.2 on a local 16k mono PCM16 speech fixture.

No real-time recording or network. 'First text' is a scheduling estimate from
measured inference times and actual chunk boundaries, not a live UI benchmark.
Reference consistency compares against full-clip ASR, NOT human-labelled WER.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import re
import sys
import time
import wave
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from localvoice.audio import Chunker
from localvoice.backend import Whisper
from localvoice.config import Settings, root_dir


class LegacyChunker(Chunker):
    def feed(self, data):
        self.parts.append(data)
        self.length += len(data)
        self.quiet = self.quiet + len(data) if np.sqrt(np.mean(data ** 2)) < .008 else 0
        if self.length >= self.rate * self.target and (self.quiet >= self.rate * .35 or self.length >= self.rate * (self.target + 3)):
            return self.flush()
        return None


def chunks(audio, chunker):
    result = []
    for start in range(0, len(audio), 800):
        block = audio[start:start + 800]
        chunk = chunker.feed(block)
        if chunk is not None:
            result.append(((start + len(block)) / 16000, chunk))
    tail = chunker.flush()
    if tail is not None:
        result.append((len(audio) / 16000, tail))
    np.testing.assert_array_equal(np.concatenate([x[1] for x in result]), audio)
    return result


def word_distance(reference, hypothesis):
    a, b = re.findall(r'\w+', reference.lower()), re.findall(r'\w+', hypothesis.lower())
    row = list(range(len(b) + 1))
    for i, token in enumerate(a, 1):
        next_row = [i]
        for j, other in enumerate(b, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1, row[j-1] + (token != other)))
        row = next_row
    return row[-1], len(a)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audio', required=True)
    parser.add_argument('--model', default='large-v3-turbo')
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--language', default='de')
    parser.add_argument('--name', default='preview')
    args = parser.parse_args()
    with wave.open(args.audio) as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)
        audio = np.frombuffer(wav.readframes(wav.getnframes()), '<i2').astype(np.float32) / 32768
    settings = Settings(model=args.model, device=args.device, language=args.language, mode='preview')
    engine = Whisper(root_dir())
    report = {'model': args.model, 'device': args.device, 'language': args.language,
              'duration_s': len(audio) / 16000, 'strategies': {}}
    try:
        begin = time.perf_counter()
        engine.start(settings)
        report['cold_load_s'] = round(time.perf_counter() - begin, 3)
        reference = engine.transcribe(audio, replace(settings, mode='final'))
        report['full_clip_reference'] = reference
        for name, chunker in [('v0.1-8s', LegacyChunker(8)), ('v0.2-4s', Chunker(4)), ('v0.2-6s', Chunker(6))]:
            outputs, timings, context = [], [], ''
            finish, first = 0.0, None
            pending = chunks(audio, chunker)
            index = 0
            while index < len(pending):
                ready, chunk = pending[index]
                index += 1
                parts = [chunk]
                count = len(chunk)
                while name != 'v0.1-8s' and index < len(pending) and pending[index][0] <= finish and count + len(pending[index][1]) <= 30 * 16000:
                    ready, extra = pending[index]
                    parts.append(extra)
                    count += len(extra)
                    index += 1
                chunk = parts[0] if len(parts) == 1 else np.concatenate(parts)
                begin = time.perf_counter()
                text = engine.transcribe(chunk, settings, prompt=context if name != 'v0.1-8s' else '')
                inference = time.perf_counter() - begin
                finish = max(ready, finish) + inference
                if text:
                    if first is None:
                        first = {'buffer_s': round(ready, 3), 'warm_first_text_s': round(finish, 3),
                                 'cold_first_text_s_estimate': round((ready + report['cold_load_s'] if name == 'v0.1-8s'
                                   else max(ready, report['cold_load_s'])) + inference, 3)}
                    outputs.append(text)
                    context = (context + ' ' + text)[-400:]
                timings.append({'ready_s': ready, 'audio_s': len(chunk) / 16000, 'inference_s': round(inference, 3), 'text': text})
            joined = ' '.join(outputs)
            differences, reference_words = word_distance(reference, joined)
            report['strategies'][name] = {'first_text': first, 'chunks': timings, 'text': joined,
                'finish_s_estimate': round(finish, 3),
                'full_clip_word_difference': differences, 'reference_word_count': reference_words}
        assert reference and all(x['text'] for x in report['strategies'].values())
        report['passed'] = True
    finally:
        engine.close()
        folder = root_dir() / 'reports'
        folder.mkdir(exist_ok=True)
        path = folder / f'{Path(args.name).name}-{args.device.replace(":", "-")}.json'
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
