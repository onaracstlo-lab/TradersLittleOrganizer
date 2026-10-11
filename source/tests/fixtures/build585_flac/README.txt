Build 585 static FLAC fingerprint fixtures

Both are single-channel, 44.1 kHz, 2003-frame native FLAC streams encoded via
libFLAC with 12- and 20-bit samples. They were independently tested with
flac -t and the new pinned-source LGPL FFmpeg PCM hashing procedure.
No libFLAC runtime dependency is needed for the tests or TLO distribution.

valid_12bit.flac: STREAMINFO FFP 3b8e898c6a51cae1b180961c1af67ac9
valid_20bit.flac: STREAMINFO FFP 958d5510f56df400e8e89709eaaa7475
