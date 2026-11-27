"""Pruebas con datos SINTÉTICOS. No constituyen resultados financieros ni evidencia T4."""

import json

import httpx
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.engine import Engine
from backend.services import Ollama, Proposal
from core.data import DataError, audit, windows
from core.simulation import backtest


@pytest.fixture
def frame():
    n = 1600
    dates = pd.date_range("2020-01-01", periods=n, tz="UTC")
    close = 100 + np.arange(n) * 0.03 + np.sin(np.arange(n) / 5)
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 0.05,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.full(n, 100.0),
        }
    )


class FakeMarket:
    def rules(self, symbol):
        return {"step": "0.0001", "minimum": 1.0}

    def price(self, symbol):
        return 100.0


class FakePredictor:
    def predict(self, symbol, frame):
        return {
            "forecast": 0.02,
            "threshold": 0.001,
            "filtered": False,
            "filter_passed": True,
            "candle": frame["date"].iloc[-1].isoformat(),
            "volatility20": 0.01,
            "distance20": 0.02,
        }


class FakeLLM:
    def __init__(self):
        self.action = "BUY"

    def propose(self, context):
        return Proposal(
            action=self.action,
            symbol=context["symbol"],
            candle=context["candle"],
            reason="Fixture sintético",
        ), 2.0


def make_engine(tmp_path):
    return Engine(
        tmp_path, market=FakeMarket(), predictor=FakePredictor(), llm=FakeLLM()
    )


@pytest.fixture
def engine(tmp_path):
    value = make_engine(tmp_path)
    value.control("start", mode="replay", symbols=["BTCUSDT"])
    return value


def cycle(engine, frame):
    return engine.cycle("BTCUSDT", frame, 100.0, {"step": ".0001", "minimum": 1.0})


def test_four_controlled_data_failures(frame):
    with pytest.raises(DataError, match="vacío"):
        audit(frame.iloc[:0])
    duplicated = pd.concat([frame, frame.iloc[:1]], ignore_index=True)
    clean, report = audit(duplicated)
    assert report["duplicate_rows_removed"] == 1
    assert len(clean) == 1600
    conflict = duplicated.copy()
    conflict.loc[len(conflict) - 1, "close"] += 0.1
    with pytest.raises(DataError, match="distintos"):
        audit(conflict)
    invalid = frame.copy()
    invalid.loc[3, "close"] = np.nan
    with pytest.raises(DataError, match="no finito"):
        audit(invalid)
    with pytest.raises(DataError, match="insuficientes"):
        windows(frame.iloc[:22])


def test_windows_and_no_future_leakage(frame):
    x, y, meta, p = windows(frame)
    assert x.shape[1:] == (20, 3)
    assert (
        meta.iloc[p["TR"].stop - 1]["target_date"]
        < meta.iloc[p["VA"].start]["target_date"]
    )
    assert (
        meta.iloc[p["VA"].stop - 1]["target_date"]
        < meta.iloc[p["TE"].start]["target_date"]
    )
    changed = frame.copy()
    changed.loc[1500:, "close"] *= 2
    x2, _, _, _ = windows(changed)
    np.testing.assert_array_equal(x[:1000], x2[:1000])
    assert pd.Timestamp(meta.iloc[0]["issue_time"]) < pd.Timestamp(
        meta.iloc[0]["target_date"]
    )


def test_api_timeout_pauses(engine, monkeypatch):
    def failure(symbol):
        raise DataError("API timeout y límite 429, tres intentos agotados")

    monkeypatch.setattr(engine.market, "recent", failure, raising=False)
    with pytest.raises(DataError, match="timeout"):
        engine.cycle("BTCUSDT")
    assert engine.state == "paused"
    assert engine.store.history()["errors"]


def test_stale_data_pauses(engine, frame):
    engine.control("start", mode="live", symbols=["BTCUSDT"])
    with pytest.raises(ValueError, match="atrasado"):
        cycle(engine, frame)
    assert engine.state == "paused"


def test_ollama_stopped_pauses(engine, frame, monkeypatch):
    def failure(context):
        raise RuntimeError("Ollama detenido")

    monkeypatch.setattr(engine.llm, "propose", failure)
    with pytest.raises(RuntimeError, match="detenido"):
        cycle(engine, frame)
    assert not engine.store.history()["decisions"]
    assert engine.state == "paused"


def test_invalid_json_and_symbol(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "{broken"}}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: Response())
    with pytest.raises(ValueError, match="JSON inválido"):
        Ollama().propose({"symbol": "BTCUSDT", "candle": "2020-01-01"})
    monkeypatch.setattr(
        Response,
        "json",
        lambda self: {
            "message": {
                "content": json.dumps(
                    {
                        "action": "BUY",
                        "symbol": "FORBIDDEN",
                        "candle": "2020-01-01",
                        "reason": "x",
                    }
                )
            }
        },
    )
    with pytest.raises(ValueError):
        Ollama().propose({"symbol": "BTCUSDT", "candle": "2020-01-01"})


def test_gateway_rejects_missing_and_wrong_key(tmp_path, monkeypatch):
    from backend import app as module

    monkeypatch.setenv("APP_API_KEY", "synthetic-test-secret-at-least-24")
    monkeypatch.setattr(module, "engine", make_engine(tmp_path))
    with TestClient(module.app) as client:
        for headers in ({}, {"X-API-Key": "wrong"}):
            assert client.get("/api/state", headers=headers).status_code == 401
            assert (
                client.post(
                    "/api/control", headers=headers, json={"action": "stop"}
                ).status_code
                == 401
            )
            assert client.get("/api/ollama/status", headers=headers).status_code == 401
        assert (
            client.get(
                "/api/state", headers={"X-API-Key": "synthetic-test-secret-at-least-24"}
            ).status_code
            == 200
        )
        assert client.post("/api/orders", json={}).status_code == 404


def test_insufficient_funds(engine, frame):
    book = "replay:llm:BTCUSDT"
    engine.store.account(book)
    with engine.store.connect() as db:
        db.execute("UPDATE accounts SET cash=.001 WHERE book=?", (book,))
    result = cycle(engine, frame)
    assert result["action"] == "REJECTED"
    assert engine.store.account(book)["quantity"] == 0


def test_duplicate_and_restart(engine, frame, tmp_path):
    cycle(engine, frame)
    assert cycle(engine, frame)["status"] == "duplicate"
    first = engine.store.account("replay:llm:BTCUSDT")
    new = make_engine(tmp_path)
    assert new.state == "paused"
    new.control("start", mode="replay", symbols=["BTCUSDT"])
    assert cycle(new, frame)["status"] == "duplicate"
    assert new.store.account("replay:llm:BTCUSDT") == first
    assert len(new.store.history()["decisions"]) == 1


def test_stop_during_llm_prevents_execution(engine, frame, monkeypatch):
    original = engine.llm.propose

    def delayed(context):
        engine.control("stop")
        return original(context)

    monkeypatch.setattr(engine.llm, "propose", delayed)
    with pytest.raises(ValueError, match="bloqueada"):
        cycle(engine, frame)
    assert not engine.store.history()["decisions"]


def test_exposure_rounding_and_no_rebuy(engine, frame):
    cycle(engine, frame)
    account = engine.store.account("replay:llm:BTCUSDT")
    assert account["quantity"] * 100 <= engine.risk.initial * engine.risk.exposure
    next_frame = frame.copy()
    next_frame["date"] += pd.Timedelta(days=1)
    assert cycle(engine, next_frame)["action"] == "HOLD"
    assert engine.store.account("replay:llm:BTCUSDT")["quantity"] == account["quantity"]


def test_sell_existing_position_only(engine, frame):
    engine.llm.action = "SELL"
    assert cycle(engine, frame)["action"] == "REJECTED"


def test_daily_loss_blocks_new_order(engine, frame):
    cycle(engine, frame)
    next_frame = frame.copy()
    next_frame["date"] += pd.Timedelta(days=1)
    result = engine.cycle(
        "BTCUSDT", next_frame, 50.0, {"step": ".0001", "minimum": 1.0}
    )
    assert result["action"] == "REJECTED"
    assert engine.state == "paused"


def test_academic_fees_and_execution_timing():
    meta = pd.DataFrame(
        {
            "issue_time": ["2020-01-01T23:59:59Z", "2020-01-02T23:59:59Z"],
            "target_date": ["2020-01-02", "2020-01-03"],
            "open": [100.0, 110.0],
            "close": [110.0, 120.0],
            "sma_filter": [True, True],
        }
    )
    table, summary = backtest(meta, np.array([0.1, 0.1]))
    expected = 100000 / (100 * 1.001) * 120 * 0.999
    assert table.iloc[-1]["equity"] == pytest.approx(expected)
    assert summary["closed_trades"] == 1
    assert summary["win_rate"] == 1.0
    assert summary["total_costs"] > 0


def test_live_api_bounded_retry(monkeypatch):
    from core.data import public_get

    calls = []

    def timeout(*args, **kwargs):
        calls.append(1)
        raise httpx.ReadTimeout("fixture")

    monkeypatch.setattr(httpx, "get", timeout)
    monkeypatch.setattr("core.data.time.sleep", lambda seconds: None)
    with pytest.raises(DataError, match="tres intentos"):
        public_get("/api/v3/klines")
    assert len(calls) == 3


def test_dqn_environment_manual_transition():
    initial, price, next_price, fee = 100000.0, 100.0, 102.0, 0.001
    quantity = initial / (price * (1 + fee))
    equity = quantity * next_price
    reward = equity - initial
    assert reward == pytest.approx(1898.1018981019)


def test_replay_20_cycles_and_three_strategy_comparison(engine, frame, tmp_path):
    from backend.evaluate_agent import compare
    from core.data import save_json

    folder = tmp_path / "artifacts/BTCUSDT"
    folder.mkdir(parents=True)
    frame.to_csv(folder / "processed.csv", index=False)
    save_json(
        folder / "freeze.json",
        {
            "test_first": frame["date"].iloc[1400].isoformat(),
            "test_last": frame["date"].iloc[1499].isoformat(),
        },
    )
    for strategy in ("llm", "model", "passive"):
        engine.control("start", mode="replay", strategy=strategy, symbols=["BTCUSDT"])
        engine.replay("BTCUSDT", 20)
    result = compare(tmp_path, "BTCUSDT")
    assert len(result) == 3
    assert result["cycles"].tolist() == [20, 20, 20]
    assert len(engine.store.history()["decisions"]) == 63
    for a in engine.store.history()["accounts"]:
        assert a["quantity"] == 0


def test_http_only_login_logout(tmp_path, monkeypatch):
    from backend import app as module

    key = "synthetic-test-secret-at-least-24"
    monkeypatch.setenv("APP_API_KEY", key)
    monkeypatch.setattr(module, "engine", make_engine(tmp_path))
    with TestClient(module.app) as client:
        assert client.get("/api/state").status_code == 401
        response = client.post("/api/session", json={"key": key})
        assert response.status_code == 200
        assert "HttpOnly" in response.headers["set-cookie"]
        assert client.get("/api/state").status_code == 200
        assert client.post("/api/logout").status_code == 200
        assert client.get("/api/state").status_code == 401


def test_t4_requirement_blocks_unverified_training(tmp_path, monkeypatch):
    from core import research
    import subprocess

    monkeypatch.setattr(research, "ROOT", tmp_path)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], 0, stdout="GPU unavailable"),
    )
    with pytest.raises(RuntimeError, match="bloqueado"):
        research.gpu_evidence()
    assert (tmp_path / "artifacts/bitacora.jsonl").exists()


def test_both_neural_architectures_save_reload_predict(tmp_path):
    from core.research import predict_saved, train_network

    rng = np.random.default_rng(101)
    x = rng.normal(0, 0.01, (80, 20, 3)).astype("float32")
    y = x[:, -1, 0] * 0.3
    for kind in ("MLP", "LSTM"):
        path = tmp_path / kind
        pt, pv, details = train_network(
            x[:60],
            y[:60],
            x[60:],
            y[60:],
            kind,
            {"units": 4, "lr": 0.001},
            101,
            path,
            max_epochs=2,
            require_t4=False,
        )
        assert details["evidence"] == "CPU_SMOKE_TEST_ONLY"
        np.testing.assert_allclose(
            pv, predict_saved(path, kind, x[60:]), rtol=1e-4, atol=1e-6
        )
        assert np.isfinite(pt).all()
        assert (path / "loss.csv").exists()


def test_research_entrypoints_freeze_test_and_future(tmp_path, frame, monkeypatch):
    from core import research
    from core.data import save_json

    monkeypatch.setattr(research, "ROOT", tmp_path)
    source = tmp_path / "data/raw"
    source.mkdir(parents=True)
    frame.to_csv(source / "BTCUSDT.csv", index=False)
    save_json(
        source / "BTCUSDT.source.json",
        {"provider": "SYNTHETIC TEST FIXTURE", "symbol": "BTCUSDT"},
    )
    research.prepare("BTCUSDT")
    original_train = research.train_network
    monkeypatch.setattr(
        research, "gpu_evidence", lambda: {"operation_device": "CPU_SMOKE_TEST_ONLY"}
    )

    def tiny_train(*args, **kwargs):
        kwargs.update(max_epochs=1, require_t4=False)
        return original_train(*args, **kwargs)

    monkeypatch.setattr(research, "train_network", tiny_train)
    research.select("BTCUSDT")
    folder = tmp_path / "artifacts/BTCUSDT"
    assert (folder / "freeze.json").exists()
    assert not (folder / "test_opened.json").exists()
    research.evaluate_test("BTCUSDT")
    future = pd.read_csv(folder / "prediccion_futura.csv")
    assert future["actual"].isna().all()
    assert pd.Timestamp(future.iloc[0]["issue_time"]) < pd.Timestamp(
        future.iloc[0]["target_date"]
    )
    assert (folder / "predicciones_TE.csv").exists()
    with pytest.raises(RuntimeError, match="ya evaluado"):
        research.evaluate_test("BTCUSDT")
    with pytest.raises(RuntimeError, match="congelada"):
        research.select("BTCUSDT")
    from core.report import generate

    assert generate(tmp_path).exists()


@pytest.mark.parametrize('hours', [8, 16])
def test_daily_session_may_open_outside_midnight(frame, hours):
    shifted = frame.copy()
    shifted['date'] += pd.Timedelta(hours=hours)
    clean, report = audit(shifted)
    pd.testing.assert_series_equal(clean['date'], shifted['date'])
    assert report['non_midnight_rows'] == len(shifted)
    assert report['opening_times_utc'] == [f'{hours:02d}:00:00.000000']
    x, y, meta, partitions = windows(clean)
    assert x.shape[1:] == (20, 3)
    assert pd.Timestamp(meta.iloc[0]['issue_time']) < pd.Timestamp(meta.iloc[0]['target_date'])


def test_irregular_edge_timestamp_is_preserved_and_logged(frame):
    shifted = frame.copy()
    shifted['date'] += pd.Timedelta(hours=16)
    shifted.loc[0, 'date'] -= pd.Timedelta(hours=3)
    clean, report = audit(shifted)
    assert report['gap_count'] == 1
    assert clean['date'].iloc[0] == shifted['date'].iloc[0]
    assert len(windows(clean)[0]) > 30


def test_intraday_data_is_rejected_even_with_shifted_session(frame):
    intraday = frame.copy()
    intraday['date'] = pd.date_range('2020-01-01', periods=len(frame), freq='4h', tz='UTC')
    with pytest.raises(DataError, match='más de una vela'):
        audit(intraday)


def test_missing_timestamp_is_rejected(frame):
    invalid = frame.copy()
    invalid.loc[0, 'date'] = pd.NaT
    with pytest.raises(DataError, match='Fecha vacía'):
        audit(invalid)


def fake_prepared_files(root, symbol, count=1600):
    from core.data import save_json
    folder = root/'artifacts'/symbol
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('processed.csv','source.json','partitions.csv','example_alignment.csv','references_TR_VA.csv','exploration.png'):
        (folder/name).write_text('synthetic-test-fixture')
    save_json(folder/'audit.json', {'valid_rows':count})


def test_universe_replaces_short_history_and_preserves_completed(tmp_path, monkeypatch):
    from core import research
    from core.data import CANDIDATES, load_catalog
    monkeypatch.setattr(research,'ROOT',tmp_path)
    fake_prepared_files(tmp_path,'BTCUSDT',1746)
    fake_prepared_files(tmp_path,'ETHUSDT',1746)
    called=[]
    def prepare_fixture(symbol):
        called.append(symbol)
        if symbol=='BNBUSDT':
            raise DataError('1316 observaciones válidas. Se requieren 1500 antes de crear ventanas.')
        fake_prepared_files(tmp_path,symbol)
    monkeypatch.setattr(research,'prepare',prepare_fixture)
    selected=research.prepare_universe()
    assert len(selected)==15 and len(set(selected))==15
    assert 'BNBUSDT' not in selected and 'AVAXUSDT' in selected
    assert 'BTCUSDT' not in called and 'ETHUSDT' not in called
    assert load_catalog(tmp_path)==tuple(selected)
    called.clear()
    assert research.prepare_universe()==selected
    assert called==[]


def test_universe_refuses_to_train_with_fewer_than_fifteen(tmp_path,monkeypatch):
    from core import research
    monkeypatch.setattr(research,'ROOT',tmp_path)
    def unavailable(symbol):
        raise DataError('Historia insuficiente del proveedor')
    monkeypatch.setattr(research,'prepare',unavailable)
    with pytest.raises(RuntimeError,match='0/15'):
        research.prepare_universe()
    assert not (tmp_path/'artifacts/asset_catalog.json').exists()
    assert (tmp_path/'artifacts/coverage.csv').exists()


def test_universe_cannot_change_after_model_selection(tmp_path,monkeypatch):
    from core import research
    monkeypatch.setattr(research,'ROOT',tmp_path)
    frozen=tmp_path/'artifacts/BTCUSDT/freeze.json'
    frozen.parent.mkdir(parents=True)
    frozen.write_text('{}')
    with pytest.raises(RuntimeError,match='congelados'):
        research.prepare_universe()


def test_catalog_rejects_repeated_assets():
    from core.data import validate_catalog
    with pytest.raises(ValueError,match='únicos'):
        validate_catalog({'selected_symbols':['BTCUSDT']*15})


def test_import_uses_selected_backup_catalog(tmp_path):
    import zipfile
    from tools.import_results import install
    from core.data import BASE_SYMBOLS, file_hash
    selected=[s for s in BASE_SYMBOLS if s!='BNBUSDT']+['AVAXUSDT']
    root=tmp_path/'destination'
    root.mkdir()
    source=tmp_path/'source.csv'
    source.write_text('synthetic-test-fixture')
    frozen={'source_sha256':file_hash(source),'selected':{'kind':'Zero','directory':''}}
    archive=tmp_path/'results.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('artifacts/asset_catalog.json',json.dumps({'selected_symbols':selected}))
        z.writestr('artifacts/AVAXUSDT/freeze.json',json.dumps(frozen))
        z.write(source,'artifacts/AVAXUSDT/processed.csv')
    install(archive,root)
    assert (root/'artifacts/asset_catalog.json').exists()
    assert (root/'artifacts/AVAXUSDT/freeze.json').exists()


def test_universe_stops_on_provider_wide_failure(tmp_path,monkeypatch):
    from core import research
    from core.data import MarketUnavailable
    monkeypatch.setattr(research,'ROOT',tmp_path)
    called=[]
    def offline(symbol):
        called.append(symbol)
        raise MarketUnavailable('HTTP 429, reintentos agotados')
    monkeypatch.setattr(research,'prepare',offline)
    with pytest.raises(MarketUnavailable,match='429'):
        research.prepare_universe()
    assert len(called)==1


@pytest.mark.parametrize('return_order', ['first', 'last', 'reverse'])
def test_pagination_recovers_full_history_under_500_candle_server_cap(monkeypatch, return_order):
    from core import data
    dates = pd.date_range('2018-06-01 16:00', periods=3200, tz='UTC')
    candles = [[int(t.timestamp()*1000), '100', '101', '99', '100', '10',
                int((t+pd.Timedelta(days=1)).timestamp()*1000)-1] for t in dates]
    calls=[]
    def capped(path, params):
        calls.append(params)
        part=[r for r in candles if params['startTime']<=r[0]<=params['endTime']]
        if return_order=='last':
            return part[-500:]
        return part[:500][::-1] if return_order=='reverse' else part[:500]
    monkeypatch.setattr(data,'public_get',capped)
    monkeypatch.setattr(data.time,'sleep',lambda seconds:None)
    result=data.fetch_daily('BTCUSDT',start='2018-01-01',end=dates[-1]+pd.Timedelta(days=1))
    assert len(result)==len(candles)
    assert result['date'].nunique()==len(candles)
    assert set(result['date'])==set(dates)
    assert all(p['endTime']-p['startTime']<200*data.DAY_MS for p in calls)
    clean, report=data.audit(result)
    assert report['missing_calendar_days']==0
    assert report['max_gap_days']==1
    assert result.attrs['download_algorithm']=='mexc-daily-paged-v2'


def test_pagination_continues_after_short_nonempty_page(monkeypatch):
    from core import data
    dates=pd.date_range('2020-01-01',periods=2000,tz='UTC')
    candles=[[int(t.timestamp()*1000),'100','101','99','100','10',int((t+pd.Timedelta(days=1)).timestamp()*1000)-1] for t in dates]
    def first_fifty(path,params):
        return [r for r in candles if params['startTime']<=r[0]<=params['endTime']][:50]
    monkeypatch.setattr(data,'public_get',first_fifty)
    monkeypatch.setattr(data.time,'sleep',lambda seconds:None)
    result=data.fetch_daily('BTCUSDT',start='2020-01-01',end=dates[-1]+pd.Timedelta(days=1))
    assert len(result)==2000
    assert data.audit(result)[1]['missing_calendar_days']==0


def test_pagination_excludes_still_open_candle(monkeypatch):
    from core import data
    start=pd.Timestamp('2020-01-01',tz='UTC')
    rows=[[int((start+pd.Timedelta(days=i)).timestamp()*1000),'100','101','99','100','10',
           int((start+pd.Timedelta(days=i+1)).timestamp()*1000)-1] for i in range(10)]
    def response(path,params):
        return [r for r in rows if params['startTime']<=r[0]<=params['endTime']]
    monkeypatch.setattr(data,'public_get',response)
    monkeypatch.setattr(data.time,'sleep',lambda seconds:None)
    end=start+pd.Timedelta(days=9,hours=12)
    result=data.fetch_daily('BTCUSDT',start='2020-01-01',end=end)
    assert len(result)==9

@pytest.mark.parametrize('position,forecast,filtered,passed,expected', [
    (0, .02, False, False, ['HOLD', 'BUY']),
    (0, -.02, False, True, ['HOLD']),
    (0, .02, True, False, ['HOLD']),
    (1, .02, False, True, ['HOLD', 'SELL']),
])
def test_local_llm_state_action_contract(monkeypatch, position, forecast, filtered, passed, expected):
    def post(url, **kwargs):
        body = kwargs['json']
        context = json.loads(body['messages'][1]['content'])
        assert context['allowed_actions'] == expected
        assert body['format']['properties']['action']['enum'] == expected
        class Response:
            def raise_for_status(self): pass
            def json(self):
                return {'message': {'content': json.dumps({
                    'action': 'HOLD', 'symbol': context['symbol'],
                    'candle': context['candle'], 'reason': 'Esperar es válido'
                })}}
        return Response()
    monkeypatch.setattr(httpx, 'post', post)
    proposal, _ = Ollama().propose({
        'symbol': 'BTCUSDT', 'candle': '2025-08-01', 'position': position,
        'cash': 50000, 'forecast': forecast, 'threshold': .001,
        'filtered': filtered, 'filter_passed': passed,
    })
    assert proposal.action == 'HOLD'  # La gramática no fuerza operaciones.


def test_invalid_sell_keeps_proposal_and_independent_risk(engine, frame):
    engine.llm.action = 'SELL'  # Fixture elude deliberadamente la gramática.
    result = cycle(engine, frame)
    assert result['action'] == 'REJECTED'
    record = engine.store.history()['decisions'][0]
    details = json.loads(record['details'])
    assert details['proposal']['action'] == 'SELL'
    assert details['proposal']['reason'] == 'Fixture sintético'
    assert details['account_before']['quantity'] == 0
    assert record['reason'] == 'No existe posición para vender'


def test_authentication_logs_no_supplied_secrets(tmp_path, monkeypatch):
    from backend import app as module
    valid = 'synthetic-valid-secret-for-private-test'
    wrong = 'synthetic-wrong-secret-for-private-test'
    monkeypatch.setenv('APP_API_KEY', valid)
    monkeypatch.setattr(module, 'engine', make_engine(tmp_path))
    with TestClient(module.app) as client:
        assert client.post('/api/session', json={'key': wrong}).status_code == 401
    errors = module.engine.store.history()['errors']
    assert errors[-1]['stage'] == 'authentication'
    serialized = json.dumps(errors)
    assert valid not in serialized and wrong not in serialized
    assert not module.engine.store.history()['decisions']


def test_invalid_json_cycle_pauses_and_records_without_trade(engine, frame, monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'message': {'content': '{invalid'}}
    monkeypatch.setattr(httpx, 'post', lambda *args, **kwargs: Response())
    engine.llm = Ollama()
    with pytest.raises(ValueError, match='JSON inválido'):
        cycle(engine, frame)
    assert engine.state == 'paused'
    history = engine.store.history()
    assert not history['decisions']
    assert 'JSON inválido' in history['errors'][-1]['detail']


def test_actual_http_429_response_has_bounded_retries(monkeypatch):
    from core.data import public_get, DataError
    calls = []
    def rate_limit(url, **kwargs):
        calls.append(1)
        return httpx.Response(429, json={'code': 429, 'msg': 'fixture rate limit'}, request=httpx.Request('GET', url))
    monkeypatch.setattr(httpx, 'get', rate_limit)
    monkeypatch.setattr('core.data.time.sleep', lambda seconds: None)
    with pytest.raises(DataError, match='tres intentos'):
        public_get('/api/v3/klines')
    assert len(calls) == 3


def test_real_order_route_is_rejected_before_network(monkeypatch):
    from core.data import public_get

    def forbidden_network(*args, **kwargs):
        pytest.fail("A forbidden order route reached the network")

    monkeypatch.setattr(httpx, "get", forbidden_network)
    with pytest.raises(DataError, match="Ruta pública no permitida"):
        public_get("/api/v3/order", {"symbol": "BTCUSDT"})
