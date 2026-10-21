import tempfile
from pathlib import Path
import json
import csv
from src.pipeline.synthetic_run import run_synthetic
from src.pipeline.analytics_run import run_analytics
from src.pipeline.backtest_run import run_backtest
from src.pipeline.export_run import export_data

def test_export_data_json_and_csv():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db_path = tmp_path / "zion.db"
        out_dir = tmp_path / "exports"

        # 1. Poblamos la base de datos temporal con datos e historial
        run_synthetic(db_path, count=5, include_broken=False)
        run_analytics(str(db_path), "BTC/USD")
        run_backtest(str(db_path), "sma_crossover", 10000.0, "BTC/USD")

        # 2. Ejecutamos export_data
        export_data(str(db_path), str(out_dir), "both")

        # 3. Verificamos la creación de archivos
        json_file = out_dir / "zion_results_export.json"
        csv_file = out_dir / "zion_results_export.csv"

        assert json_file.exists()
        assert csv_file.exists()

        # 4. Validamos contenido del archivo JSON
        data_json = json.loads(json_file.read_text(encoding="utf-8"))
        assert len(data_json) >= 2
        kinds = {item["kind"] for item in data_json}
        assert "analytics" in kinds
        assert "backtest" in kinds

        # 5. Validamos contenido del archivo CSV
        with open(csv_file, mode="r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            assert len(reader) >= 2
            csv_kinds = {row["kind"] for row in reader}
            assert "analytics" in csv_kinds
            assert "backtest" in csv_kinds
