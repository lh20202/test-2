# Bach MusicXML loop prototype

This local prototype uses one MusicXML file from the Bach Chorales Figured Bass dataset:

https://github.com/juyaolongpaul/Bach_chorale_FB

Test source used:

`FB_source/musicXML_master/BWV_93.07_FB.musicxml`

Local copy:

`data/input/bach-test.musicxml`

Run the extractor:

```sh
python3 scripts/extract_loops.py
```

Output:

`data/output/loops.json`

The extractor uses only Python's standard library. No extra dependency install is required.
