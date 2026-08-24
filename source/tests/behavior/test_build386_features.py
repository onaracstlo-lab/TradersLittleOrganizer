from pathlib import Path
import tlo_phase23_v2 as phase

def test_build386_main_console_has_horizontal_scrollbar():
    source = Path(phase.__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    assert 'self.output = tk.Text(output_frame' in source
    assert 'wrap="none"' in source
    assert 'orient="horizontal", command=self.output.xview' in source
