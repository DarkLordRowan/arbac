import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
import pytest

pa=pytest.importorskip("pyarrow")
from arbac_research import storage
from arbac_research.metrics import summarize_task


def test_round_trip_high_precision_zstd(tmp_path):
    p=tmp_path/"trace"/"part-test.parquet"
    value="1.000000000000000000000000000000000000000000000009"
    rows=[dict(task_id="x",row_type="baseline",n_used=1,k=None,value="1.1",
               exact_sum="1",dps=100,accel_id="w",status="ok"),
          dict(task_id="x",row_type="accel",n_used=1,k=0,value=value,
               base_value="1.1",exact_sum="1",dps=100,accel_id="w",status="ok")]
    storage.write_trace(p,rows)
    restored=list(storage.iterate_tasks(tmp_path))
    assert restored[0][1]["value"]==value
    assert float(summarize_task(restored[0])["gain_best_orders"])>40
    assert storage.inspect(tmp_path)["rows"]==2
