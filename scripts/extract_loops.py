#!/usr/bin/env python3
"""Extract one producer-ready 8-bar loop from a Bach MusicXML file."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "input" / "bach-test.musicxml"
OUTPUT = ROOT / "data" / "output" / "loops.json"

FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
STEP_TO_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
ALTER_TO_TEXT = {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}


def text_int(node: ET.Element | None, default: int = 0) -> int:
    if node is None or node.text is None:
        return default
    try:
        return int(float(node.text.strip()))
    except ValueError:
        return default


def pitch_to_midi(pitch: ET.Element) -> int:
    step = pitch.findtext("step", "C").strip()
    alter = text_int(pitch.find("alter"), 0)
    octave = text_int(pitch.find("octave"), 4)
    return (octave + 1) * 12 + STEP_TO_PC[step] + alter


def midi_to_note(midi: int) -> str:
    octave = midi // 12 - 1
    return f"{FLAT_NAMES[midi % 12]}{octave}"


def move_to_midrange(midi: int, low: int = 43, high: int = 72) -> int:
    while midi < low:
        midi += 12
    while midi > high:
        midi -= 12
    return midi


def simplify_stack(midis: list[int]) -> list[str]:
    if not midis:
        return []

    by_pitch_class: dict[int, list[int]] = defaultdict(list)
    for midi in midis:
        shifted = move_to_midrange(midi)
        by_pitch_class[shifted % 12].append(shifted)

    compact = []
    for values in by_pitch_class.values():
        compact.append(min(values, key=lambda value: abs(value - 58)))

    compact = sorted(set(compact))

    if len(compact) > 4:
        bass = min(compact)
        upper = sorted(compact[1:], key=lambda value: abs(value - 62))[:3]
        compact = sorted([bass, *upper])

    while compact and max(compact) - min(compact) > 24:
        compact[-1] -= 12
        compact = sorted(compact)

    return [midi_to_note(midi) for midi in compact[:4]]


def parse_musicxml(path: Path) -> list[dict[str, float | int]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input file: {path}")

    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise RuntimeError(f"Could not parse MusicXML: {exc}") from exc

    root = tree.getroot()
    notes: list[dict[str, float | int]] = []

    for part in root.findall("part"):
        divisions = 1
        cursor_beats = 0.0

        for measure in part.findall("measure"):
            for child in measure:
                if child.tag == "attributes":
                    divisions = text_int(child.find("divisions"), divisions) or divisions
                    continue

                if child.tag == "backup":
                    cursor_beats -= text_int(child.find("duration"), 0) / divisions
                    continue

                if child.tag == "forward":
                    cursor_beats += text_int(child.find("duration"), 0) / divisions
                    continue

                if child.tag != "note":
                    continue

                duration_beats = text_int(child.find("duration"), 0) / divisions
                is_chord = child.find("chord") is not None
                pitch = child.find("pitch")

                if pitch is not None and child.find("rest") is None:
                    start = cursor_beats if not is_chord else cursor_beats - duration_beats
                    notes.append(
                        {
                            "time": max(0.0, start),
                            "duration": max(0.25, duration_beats),
                            "midi": pitch_to_midi(pitch),
                        }
                    )

                if not is_chord:
                    cursor_beats += duration_beats

    return notes


def build_loop(notes: list[dict[str, float | int]]) -> list[dict[str, object]]:
    if not notes:
        raise RuntimeError("No pitched notes found in MusicXML.")

    grouped: dict[float, list[int]] = defaultdict(list)
    for note in notes:
        beat = round(float(note["time"]) * 2) / 2
        grouped[beat].append(int(note["midi"]))

    strong_beats = sorted(beat for beat in grouped if beat >= 0)
    if not strong_beats:
        raise RuntimeError("No quantised note groups found in MusicXML.")

    pickup_offset = min(strong_beats)
    candidates: list[tuple[float, list[int]]] = []
    for bar in range(8):
        downbeat = pickup_offset + bar * 4
        options = [
            beat
            for beat in strong_beats
            if downbeat <= beat < downbeat + 4
        ]
        if not options:
            continue

        chosen = min(options, key=lambda value: abs(value - downbeat))
        candidates.append((bar * 4, grouped[chosen]))

    events = []
    last_notes: list[str] | None = None
    for index, (time, midis) in enumerate(candidates[:8]):
        notes_out = simplify_stack(midis)
        if not notes_out:
            continue

        if notes_out == last_notes and len(midis) > 3:
            notes_out = simplify_stack([midi + 12 if i % 2 else midi for i, midi in enumerate(midis)])

        next_time = candidates[index + 1][0] if index + 1 < len(candidates[:8]) else 32
        duration = max(1, min(4, next_time - time))
        events.append({"time": int(time), "notes": notes_out, "duration": int(duration)})
        last_notes = notes_out

    if len(events) < 2:
        raise RuntimeError("Could not derive enough chord events for an 8-bar loop.")

    return events


def main() -> int:
    try:
      notes = parse_musicxml(INPUT)
      loop = build_loop(notes)
      OUTPUT.parent.mkdir(parents=True, exist_ok=True)
      payload = [
          {
              "id": "bach-test-001",
              "source": {
                  "composer": "J. S. Bach",
                  "work": "Bach chorale test",
                  "file": "bach-test.musicxml",
              },
              "vibe": ["emotional loop", "ambient", "melodic"],
              "bpm": 120,
              "bars": 8,
              "loop": loop,
          }
      ]
      OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
      print(f"Wrote {OUTPUT}")
      return 0
    except Exception as exc:
      print(f"extract_loops.py: {exc}", file=sys.stderr)
      return 1


if __name__ == "__main__":
    raise SystemExit(main())
