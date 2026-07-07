__version__ = "v320"
# TLO-GI package version: v320
__version_summary__ = 'Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.'
# TLO-GI version summary: Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Candidate:
    value: str
    source: str
    confidence: int


@dataclass
class ShowMetadata:
    group_number: int
    main_dir_name: str
    main_dir_path: str
    setlist_file: str
    music_file_count: int
    setlist_files: List[str] = field(default_factory=list)
    music_dirs: List[str] = field(default_factory=list)
    volume_label: str = ""
    artist: str = ""
    date: str = ""
    venue: str = ""
    city: str = ""
    region: str = ""
    country: str = ""
    location: str = ""
    qualifier: str = ""
    parentheticals: str = ""
    album_name: str = ""
    is_24_bit: bool = False
    show_name: str = ""
    show_in_conflict: bool = False
    conflicts: List[str] = field(default_factory=list)
    evidence: Dict[str, List[Candidate]] = field(default_factory=dict)
    flac_tag_samples: List[dict] = field(default_factory=list)
    flac_tag_artist_values: List[str] = field(default_factory=list)
    flac_tag_album_values: List[str] = field(default_factory=list)
    flac_tag_albumartist_values: List[str] = field(default_factory=list)
    flac_tag_date_values: List[str] = field(default_factory=list)
    setlistfm_setlist_candidates: List[Dict[str, object]] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
