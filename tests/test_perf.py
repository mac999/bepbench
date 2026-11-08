"""Performance regression budget for the IFC path.

Generates a synthetic model and fails when tessellation time or payload size per
element crosses the budget in ``perf.*``. Skipped unless ``BEP_PERF=1``, so the
ordinary suite stays fast; CI sets it.
"""

import os
import time

import pytest

from bepkit.ids import IFCTESTER_AVAILABLE
from bepkit.settings import get as setting

pytestmark = [
    pytest.mark.skipif(os.environ.get("BEP_PERF") != "1", reason="set BEP_PERF=1 to run"),
    pytest.mark.skipif(not IFCTESTER_AVAILABLE, reason="ifcopenshell not installed"),
]


def test_tessellation_stays_within_budget(tmp_path):
    from bepkit.ifcio.loader import inspect_file, tessellate
    from bepkit.ifcio.synthetic import write_grid_model

    elements = int(setting("perf.elements", 1000))
    started = time.perf_counter()
    source = write_grid_model(tmp_path / "grid.ifc", elements)
    generated = time.perf_counter() - started
    assert generated < setting("perf.max_generate_seconds", 30), f"generation took {generated:.1f}s"

    started = time.perf_counter()
    meta = tessellate(source, tmp_path / "model.bin", tmp_path / "model.json")
    seconds = time.perf_counter() - started
    per_thousand = seconds * 1000 / elements
    buffer_per_element = (tmp_path / "model.bin").stat().st_size / elements
    index_per_element = (tmp_path / "model.json").stat().st_size / elements
    print(f"\nperf: {elements} elements, tessellate {seconds:.2f}s "
          f"({per_thousand:.2f}s per 1000), {buffer_per_element:.0f} B/element buffer, "
          f"{index_per_element:.0f} B/element index")

    assert meta["element_count"] == elements and not meta["truncated"]
    assert per_thousand < setting("perf.max_tessellate_seconds_per_1000", 6), f"{per_thousand:.2f}s per 1000"
    assert buffer_per_element < setting("perf.max_buffer_bytes_per_element", 2000)
    assert index_per_element < setting("perf.max_index_bytes_per_element", 400)

    summary = inspect_file(source)
    assert summary["element_count"] >= elements


def test_the_cap_truncates_instead_of_growing(tmp_path):
    from bepkit.ifcio.loader import tessellate
    from bepkit.ifcio.synthetic import write_grid_model

    source = write_grid_model(tmp_path / "small.ifc", 60, storeys=2)
    meta = tessellate(source, tmp_path / "m.bin", tmp_path / "m.json", max_elements=25)
    assert meta["truncated"] and meta["element_count"] == 25
