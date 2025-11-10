from database import DB_PATH,fetch_latest, fetch_last_n,fetch_last_n_raw, init_db 
from flask import Flask, jsonify, request, render_template, Response, g, current_app
import sqlite3,logging, json, uuid
from models.isolation import fit_iforest, score_iforest
import numpy as np
from io import BytesIO
from datetime import datetime, timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from time import perf_counter, monotonic, time

from retention import run_retention
from models.lstm import load_artifacts, make_sequences, score_sequences
from dotenv import load_dotenv

def get_setting(key: str, default: str | None = None) -> str | None:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default

def set_setting(key: str, value: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )
        conn.commit()


def detect_scores(X: np.ndarray, model: str, contamination: float):
    """Detects anomalies using the specified model."""

    app = current_app 
    m = (model or "iforest").lower()
    if m == "lstm":
        try:
            
            lstm_cache = app.config['_lstm_cache']
            if not lstm_cache["loaded"]:
                mdl, s, L = load_artifacts()
                lstm_cache.update({"loaded": True, "model": mdl, "scaler": s, "seq_len": L})
            
            mdl, s, L = lstm_cache["model"], lstm_cache["scaler"], lstm_cache["seq_len"]
            Xs = s.transform(X)
            if len(Xs) < L:
                scores = np.zeros(len(Xs), dtype=float)
                is_out = np.zeros(len(Xs), dtype=bool)
                return scores, is_out, "lstm"
            S = make_sequences(Xs, L)
            errs = score_sequences(mdl, S)
            scores = np.zeros(len(Xs), dtype=float)
            scores[L-1:] = errs
            k = max(1, int(np.ceil(len(scores) * min(max(contamination, 0.001), 0.5))))
            thresh = np.partition(scores, -k)[-k]
            is_out = scores >= thresh
            return scores, is_out, "lstm"
        
        except Exception as e:
        
            app.logger.warning(json.dumps({"lstm_inference_error": str(e)}))
            # Fallback to iforest if LSTM fails
            clf = fit_iforest(X, contamination=contamination, random_state=42)
            scores_vals, is_out = score_iforest(clf, X)
            return scores_vals, is_out, "iforest"


        # Default: Isolation Forest
    clf = fit_iforest(X, contamination=contamination, random_state=42)
    scores_vals, is_out = score_iforest(clf, X)
    return scores_vals, is_out, "iforest"


def create_app():
    """
    Creates and configures a new Flask application instance.
    This "application factory" pattern is a best practice that makes the app
    more modular and easier to test and configure.
    """
    
    # Load environment variables from a .env file at the start.
    load_dotenv()

    app = Flask(__name__)

    
    # These are kept inside the factory to avoid global scope issues.
    app.config.update(
        _last_fit={"counter": 0, "clf": None, "n": None, "c": None, "Xshape": None},
        REPLAY_MODE=False,
        _replay_index=0,
        REPLAY_STRIDE=5,
        _last_manual_step_at=0.0,
        _lstm_cache={"loaded": False, "model": None, "scaler": None, "seq_len": None},
        _metrics={
            "requests_total": 0, "latency_ms_sum": 0.0, "latency_ms_count": 0,
            "rows_total": 0, "anomalies_24h": 0, "errors_total": 0, "last_error_ts": None,
        }
    )

    # Configure logging
    # We do this inside the factory to attach the logger to this specific app instance.
    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)


    def total_rows():
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM readings")
            return int(cur.fetchone()[0] or 0)


    def fetch_window_at_index(n: int, end_index: int):
        start = max(0, end_index - n)
        limit = max(1 if end_index > 0 else 0, min(n, end_index - start))
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM readings ORDER BY id ASC LIMIT ? OFFSET ?", (limit, start))
            return [dict(r) for r in cur.fetchall()]


    def init_settings_table():
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            defaults = {"replay_stride": str(app.config['REPLAY_STRIDE'])} # Add others
            for k, v in defaults.items():
                cur.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (k, v))
            conn.commit()
        
    def load_persisted_defaults():
        try:
            app.config['REPLAY_STRIDE'] = int(get_setting("replay_stride", str(app.config['REPLAY_STRIDE'])))
        except Exception as e:
            app.logger.warning(json.dumps({"config_load_warning": str(e)}))




    def step_replay_index(stride: int):
        max_id = total_rows()
        idx = app.config['_replay_index']
        if idx >= max_id:
            return idx
        app.config['_replay_index'] = min(idx + stride, max_id)
        return app.config['_replay_index']




    @app.route("/")  # Root route to serve the dashboard pag
    def index():
        # render_template looks in the 'templates' folder for 'index.html'.
        return render_template("index.html")  # Returns the HTML dashboard page.

    @app.route("/latest", methods=["GET"])
    def latest():
        row = fetch_latest()
        return (jsonify(row), 200) if row else (jsonify({"message": "no data"}), 404)

    @app.post("/mode")
    def set_mode():
        payload = request.get_json(silent=True) or {}
        is_replay = payload.get("mode") == "replay"
        app.config['REPLAY_MODE'] = is_replay
        if is_replay:
            app.config['_replay_index'] = 0
        return jsonify({
            "mode": "replay" if is_replay else "live",
            "index": app.config['_replay_index']
        }), 200



    

    



    @app.post("/admin/retention")
    def admin_retention():
    
        days = request.args.get("days", default="7")
        try:
            d = int(days)
            run_retention(retain_days=d)
            return jsonify({"ok": True, "retained_days": d}), 200
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500


    @app.get("/config")
    def get_config():
        keys = ["contamination_default","replay_stride","history_window_default",
                "score_window_default","poll_ms","default_model","view_window_seconds"]
        
        out = { k: get_setting(k) for k in keys }
        # --- FIX #2: Use app.config for state ---
        out["replay_mode"] = app.config['REPLAY_MODE']
        out["replay_index"] = app.config['_replay_index']
        return jsonify(out), 200

    @app.post("/config")
    def set_config():
        payload = request.get_json(silent=True) or {}
        allowed = {"contamination_default","replay_stride","history_window_default",
                "score_window_default","poll_ms","default_model","view_window_seconds"}
        updated, errors = {}, {}
        
        for k, v in payload.items():
            if k not in allowed:
                continue
            
            
            try:
                if k == "default_model":
                    if str(v).lower() not in {"iforest","lstm"}:
                        raise ValueError("model must be iforest|lstm")
                
                elif k == "contamination_default": 
                    float(v)  # Validate it's a float
                elif k in {"replay_stride", "history_window_default", "score_window_default", "poll_ms", "view_window_seconds"}: 
                    int(v)  # Validate it's an int
                
                # If all validations pass, set the setting
                set_setting(k, str(v))
                if k == 'replay_stride':
                    app.config['REPLAY_STRIDE'] = int(v)
                elif k == 'contamination_default':
                    app.config['CONTAMINATION_DEFAULT'] = float(v)
                updated[k] = v
                
            except Exception as e:
                errors[k] = str(e)
                
        

        return jsonify({"ok": True, "updated": updated, "errors": errors}), 200




    @app.post("/replay/reset")
    def replay_reset():
        app.config['_replay_index'] = 0
        return jsonify({"ok": True, "index": 0}), 200


    

    def _get_last_id(conn):
        cur = conn.execute("SELECT MAX(id) FROM readings")
        r = cur.fetchone()
        return int(r[0] or 0)



    # in /replay/step, record the manual step time just before returning
    @app.route('/replay/step', methods=['POST'])
    def replay_step():
        if not app.config['REPLAY_MODE']:
            app.config['REPLAY_MODE'] = True
        
        data = request.get_json(silent=False) or {}
        delta = data.get('delta', 0)
        if not isinstance(delta, int):
            return jsonify(error='delta must be int'), 400

        max_id = total_rows()
        current_index = app.config['_replay_index']
        next_index = max(0, min(current_index + delta, max_id))
        
        app.config['_replay_index'] = next_index
        app.config['_last_manual_step_at'] = monotonic()
        
        return jsonify(ok=True, index=next_index)




    @app.get("/replay/seek")
    def replay_seek():
        ts = request.args.get("ts")
        if not ts:
            return jsonify({"ok": False, "error": "missing ts"}), 400
        try:
            # Accept either Z or offset; normalize to UTC ISO for SQLite
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
            iso = dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            return jsonify({"ok": False, "error": "bad ts format"}), 400

       
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT id FROM readings WHERE timestamp >= ? ORDER BY id ASC LIMIT 1",
                (iso,)
            )
            row = cur.fetchone()
            if row:
                app.config['_replay_index'] = int(row["id"])
            else:
                last_id_cur = conn.execute("SELECT MAX(id) FROM readings")
                app.config['_replay_index'] = int(last_id_cur.fetchone()[0] or 0)
        app.config['_last_manual_step_at'] = monotonic()
        return jsonify({"ok": True, "index": app.config['_replay_index']})
    



    @app.route("/history", methods=["GET"])
    def history():
        n_param = request.args.get("n", default="100")
        try:
            n = int(n_param)
        except ValueError:
            return jsonify({"error": "n must be an integer"}), 400
        n = max(1, min(n, 2000))

        if app.config['REPLAY_MODE']:
            # Auto-advance unless a manual step occurred very recently
            if monotonic() - app.config['_last_manual_step_at'] > 0.5:
                step_replay_index(app.config['REPLAY_STRIDE'])

            rows = fetch_window_at_index(n, app.config['_replay_index'])  # oldest->newest
            replay_now = 0
            if rows:
                newest_iso = rows[-1]["timestamp"]
                replay_now = int(datetime.fromisoformat(newest_iso.replace("Z", "+00:00"))
                                    .astimezone(timezone.utc).timestamp() * 1000)
            else:
                # fallback: anchor clock to newest DB timestamp
                with sqlite3.connect(DB_PATH) as conn:
                    cur = conn.execute("SELECT MAX(timestamp) FROM readings")
                    newest_iso = cur.fetchone()[0]
                    if newest_iso:
                        replay_now = int(datetime.fromisoformat(newest_iso.replace("Z", "+00:00"))
                                            .astimezone(timezone.utc).timestamp() * 1000)
            return jsonify({"rows": rows, "replay_now": replay_now, "server_now": int(time() * 1000)}), 200

        else:
            rows = fetch_last_n(n)
            rows = sorted(rows, key=lambda r: r["timestamp"])  # oldest->newest
            return jsonify({"rows": rows, "server_now": int(time() * 1000)}), 200



    

    











    @app.get("/healthz")
    def healthz():
        m = app.config['_metrics']
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM readings")
                rows = int(cur.fetchone()[0] or 0)
                cur.execute("SELECT MAX(timestamp) FROM readings")
                last_ts = cur.fetchone()[0]
            m["rows_total"] = rows
            return jsonify({
                "ok": True, "rows": rows, "last_ts": last_ts,
                "replay_mode": app.config['REPLAY_MODE'],
                "replay_index": app.config['_replay_index'],
                "db_path": DB_PATH,
            }), 200
        except Exception as e:
            m["errors_total"] += 1
            m["last_error_ts"] = datetime.utcnow().isoformat()
            app.logger.error(json.dumps({"rid": getattr(g, "request_id","-"), "health_error": str(e)}))
            return jsonify({"ok": False, "error": str(e)}), 500



    @app.get("/metrics")
    def metrics():
        m = app.config['_metrics']
        # Average latency
        if m["latency_ms_count"] > 0:
            avg_latency = m["latency_ms_sum"] / m["latency_ms_count"]
        else:
            avg_latency = 0.0
            

        # Count anomalies in last 24 hours (approx; adjust table/column names if needed)
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                # If you do not persist anomalies in a table, approximate using readings + your model
                # For now, we estimate by scanning a recent window (fast and simple)
                cur.execute("""
                    SELECT COUNT(*) FROM readings
                    WHERE timestamp >= datetime('now','-24 hours') 
                """)
                last_24h_rows = int(cur.fetchone()[0] or 0)
        except Exception:
            last_24h_rows = 0

        try:
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM hourly_aggregates")
                aggregates_rows = int(cur.fetchone()[0] or 0)
        except Exception:
            aggregates_rows = 0
        



        payload = {
            "requests_total": m["requests_total"],
            "rows_total": m["rows_total"],
            "anomalies_24h": m.get("anomalies_24h", 0),
            "avg_latency_ms": round(avg_latency, 2),
            "last_24h_rows": last_24h_rows,
            "errors_total": m.get("errors_total", 0),
            "last_error_ts": m.get("last_error_ts"),
            "hourly_aggregates_total": aggregates_rows,
        }

        return jsonify(payload), 200


    @app.get("/ping")
    def ping():
        return jsonify({"ok": True}), 200



    @app.get("/scores")
    def scores():
        try:
            n = int(request.args.get("n", "200"))

        except ValueError:
            return jsonify({"error": "n must be an integer"}), 400
        
        n = max(1, min(n, 2000))

        if app.config['REPLAY_MODE']:
            # align with the same replay slice shown on charts
            rows = fetch_window_at_index(n, app.config['_replay_index'])  # oldest->newest
        else:
            rows = fetch_last_n_raw(n)                      # newest-first (live)

        if not rows:
            return jsonify([]), 200

        model = request.args.get("model", get_setting("default_model", "iforest")).lower()

        X = np.array([[r["temperature"], r["pressure"], r["motor_speed"]] for r in rows], dtype=float)
        c = float(request.args.get("c", "0.05"))
        c = max(0.001, min(c, 0.5))

        scores_vals, is_out, used = detect_scores(X, model=model, contamination=c)

        out = []
        for r, s, o in zip(rows, scores_vals, is_out):
            r2 = dict(r)
            r2["anomaly_score"] = float(s)
            r2["is_anomaly"] = bool(o)
            r2["model"] = used
            out.append(r2)
        return jsonify(out), 200



    @app.get("/anomalies")
    def anomalies():
        try:
            n = int(request.args.get("n", "200"))

        except ValueError:
            return jsonify({"error": "n must be an integer"}), 400
        
        n = max(1, min(n, 2000))
        if app.config['REPLAY_MODE']:
            rows = fetch_window_at_index(n,app.config['_replay_index'])  # oldest->newest
        else:
            rows = fetch_last_n_raw(n)                      # newest-first

        if not rows:
            return jsonify([]), 200

        model = request.args.get("model", get_setting("default_model", "iforest")).lower()

        X = np.array([[r["temperature"], r["pressure"], r["motor_speed"]] for r in rows], dtype=float)
        c = float(request.args.get("c", "0.05")); c = max(0.001, min(c, 0.5))

        scores_vals, is_out, used = detect_scores(X, model=model, contamination=c)

        flagged = []
        for r, s, o in zip(rows, scores_vals, is_out):
            if o:
                r2 = dict(r)
                r2["anomaly_score"] = float(s)
                r2["is_anomaly"] = True
                r2["model"] = used
                flagged.append(r2)
        return jsonify(flagged), 200



    @app.get("/scores_for_window")
    def scores_for_window():
        try:
            n = int(request.args.get("n", "90"))

        except ValueError:
            return jsonify({"error":"n must be int"}), 400
        
        n = max(1, min(n, 2000))

        if app.config['REPLAY_MODE']:
            rows = fetch_window_at_index(n, app.config['_replay_index'])  
        else:
            rows = fetch_last_n(n)
            rows = sorted(rows, key=lambda r: r["timestamp"])

        if not rows:
            return jsonify([]), 200

        model = request.args.get("model", get_setting("default_model", "iforest")).lower()
        X = np.array([[r["temperature"], r["pressure"], r["motor_speed"]] for r in rows], dtype=float)
        c = float(request.args.get("c", "0.05"))
        c = max(0.001, min(c, 0.5))

        
        scores_vals, is_out, used = detect_scores(X, model=model, contamination=c)

        out = []
        for r, s, o in zip(rows, scores_vals, is_out):
            r2 = dict(r)
            r2["anomaly_score"] = float(s)
            r2["is_anomaly"] = bool(o)
            r2["model"] = used
            out.append(r2)  
        return jsonify(out), 200    




    @app.get("/export")
    def export_csv():
        

        # Accept either last n or a [from, to] ISO8601 UTC window
        from_ts = request.args.get("from")
        to_ts = request.args.get("to")
        n_param = request.args.get("n", "200")

        try:
            if from_ts and to_ts:
                # Validate and normalize to UTC ISO
                dt_from = datetime.fromisoformat(from_ts.replace("Z", "+00:00")).astimezone(timezone.utc)
                dt_to = datetime.fromisoformat(to_ts.replace("Z", "+00:00")).astimezone(timezone.utc)
                iso_from = dt_from.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
                iso_to = dt_to.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
                with sqlite3.connect(DB_PATH) as conn:
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT id, timestamp, temperature, pressure, motor_speed
                        FROM readings
                        WHERE timestamp BETWEEN ? AND ?
                        ORDER BY timestamp ASC
                    """, (iso_from, iso_to))
                    rows = [dict(r) for r in cur.fetchall()]
            else:
                n = int(n_param)
                n = max(1, min(n, 2000))
                rows = fetch_last_n(n)  # oldest->newest
        except ValueError:
            return jsonify({"error": "bad parameters: use n or from/to ISO8601"}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        import csv, io
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["id","timestamp","temperature","pressure","motor_speed"])
        writer.writeheader()
        for r in rows or []:
            writer.writerow(r)
        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=history.csv"}
        )



    @app.get("/report")
    def report_pdf():
        from_ts = request.args.get("from")
        to_ts = request.args.get("to")
        try:
            n = int(request.args.get("n", "120"))
        except ValueError:
            n = 120
        try:
            c = float(request.args.get("c", "0.05"))
        except ValueError:
            c = 0.05
        c = max(0.001, min(c, 0.5))

        try:
            if from_ts and to_ts:
                dt_from = datetime.fromisoformat(from_ts.replace("Z", "+00:00")).astimezone(timezone.utc)
                dt_to = datetime.fromisoformat(to_ts.replace("Z", "+00:00")).astimezone(timezone.utc)
                iso_from = dt_from.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
                iso_to = dt_to.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
                with sqlite3.connect(DB_PATH) as conn:
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT id, timestamp, temperature, pressure, motor_speed
                        FROM readings
                        WHERE timestamp BETWEEN ? AND ?
                        ORDER BY timestamp ASC
                    """, (iso_from, iso_to))
                    rows = [dict(r) for r in cur.fetchall()]
                rows_nf = list(reversed(rows))  # newest-first for scoring
            else:
                rows = fetch_last_n(n)          # oldest->newest
                rows_nf = fetch_last_n_raw(n)   # newest-first
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        if rows_nf:
            X = np.array([[r["temperature"], r["pressure"], r["motor_speed"]] for r in rows_nf], dtype=float)
            clf = fit_iforest(X, contamination=c, random_state=42)
            scores_vals, is_out = score_iforest(clf, X)
        else:
            scores_vals, is_out = [], []

        anom_count = int(sum(is_out)) if len(is_out) else 0
        latest = rows[-1] if rows else None

        table_rows = []
        for r, s, o in zip(rows_nf, scores_vals, is_out):
            if o:
                table_rows.append([
                    r["timestamp"],
                    f'{float(r["temperature"]):.2f}',
                    f'{float(r["pressure"]):.2f}',
                    f'{int(r["motor_speed"])}',
                    f'{float(s):.3f}',
                ])
        table_rows = table_rows[:40000]

        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm, topMargin=14*mm, bottomMargin=14*mm)
        styles = getSampleStyleSheet()
        story = []

        title = Paragraph("Anomaly Report", styles['Title'])
        range_text = (f'Range: {from_ts} → {to_ts}' if from_ts and to_ts
                    else f'Window: last {n} points')
        meta = Paragraph(
            f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} &nbsp;&nbsp; '
            f'{range_text} &nbsp;&nbsp; Contamination: {c:.3f}',
            styles['Normal']
        )
        story += [title, Spacer(1, 6), meta, Spacer(1, 8)]

        kpi_lines = []
        if latest:
            kpi_lines.append(f'Latest Temp: {float(latest["temperature"]):.2f}')
            kpi_lines.append(f'Latest Pressure: {float(latest["pressure"]):.2f}')
            kpi_lines.append(f'Latest RPM: {int(latest["motor_speed"])}')
        kpi_lines.append(f'Anomalies in window: {anom_count}')
        story += [Paragraph(" | ".join(kpi_lines), styles['Heading3']), Spacer(1, 6)]

        data = [["Time", "Temp (°C)", "Pressure (bar)", "RPM", "Score"]] + table_rows
        tbl = Table(data, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#111a2a")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#1e2a40")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#0b1320"), colors.HexColor("#0e1827")]),
            ("TEXTCOLOR", (0,1), (-1,-1), colors.HexColor("#e6eef7")),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ALIGN", (1,1), (-2,-1), "RIGHT"),
        ]))
        story += [Paragraph("Recent anomalies", styles['Heading2']), Spacer(1, 4), tbl]

        doc.build(story)
        pdf_bytes = buf.getvalue()
        buf.close()
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment; filename=anomaly_report.pdf"}
        )
    
    @app.before_request
    def before_request_hook():
        g._t0 = perf_counter()
        g.request_id = str(uuid.uuid4())

    @app.after_request
    def after_request_hook(resp):
        m = app.config['_metrics']
        ms = (perf_counter() - getattr(g, "_t0", perf_counter())) * 1000.0
        m["requests_total"] += 1
        m["latency_ms_sum"] += ms
        m["latency_ms_count"] += 1
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Response-Time"] = f"{ms:.2f}ms"
        app.logger.info(json.dumps({
            "rid": g.request_id, "method": request.method, "path": request.path,
            "status": resp.status_code, "ms": round(ms, 2),
        }))
        return resp
    

    with app.app_context():
        init_db()
        init_settings_table()
        load_persisted_defaults()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True) # starts a server on http://127.0.0.1:5000
