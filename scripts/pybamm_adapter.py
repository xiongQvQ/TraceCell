#!/usr/bin/env python3
"""PyBaMM bridge: human-reviewed JSON -> isothermal DFN -> simulate -> calibrate.

Stages
  apply   reviewed scalars/functions/curves onto a baseline parameter set
          (Chen2020 fallback, CONSPICUOUSLY LABELED as HYBRID when gaps remain)
  --run   1C CC discharge (or --c-rate/--cut-voltage), writes V(capacity) CSV+PNG
  --calibrate --target digitized_1C.csv --fit id[:mode],...   "自动仿真训练":
          bounded least-squares of selected reviewed parameters against the
          digitized experimental curve. Fitted values are CALIBRATED, never
          VERIFIED — they are simulation fits, not paper evidence.

Integrity: functions from expr://sym (SymPy) and data://curve (human-calibrated
CSV) are compiled to PyBaMM callables; nothing is silently filled by code.
"""
import argparse, csv, json, math, sys
from pathlib import Path


def read_curve_csv(path):
    rows = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.startswith('#') or not line.strip():
            continue
        parts = line.split(',')
        try:
            rows.append((float(parts[0]), float(parts[1])))
        except (ValueError, IndexError):
            continue  # header row
    return rows


def sympy_to_pybamm(expr_str, const_symbols=None):
    """Compile '8.794e-11*exp(-0.65*ce/ce_ref)' into a PyBaMM-safe callable."""
    import sympy as sp
    import pybamm
    const_symbols = const_symbols or {}
    expr = sp.sympify(expr_str)
    # numeric constants (e.g. reference concentrations) substituted first
    subs = {}
    for s in expr.free_symbols:
        if str(s) in const_symbols:
            subs[s] = sp.Float(const_symbols[str(s)])
    expr = expr.subs(subs)
    syms = sorted((s for s in expr.free_symbols), key=lambda s: str(s))
    if len(syms) != 1:
        raise ValueError(f'expected exactly 1 free variable after substitution, got {[str(s) for s in syms]}')
    var = syms[0]
    body = str(expr)
    # PyBaMM's math-function surface varies across versions — probe it.
    _CANDIDATES = {'exp': ['exp'], 'log': ['log'], 'sqrt': ['sqrt'],
                   'Abs': ['abs', 'AbsoluteValue'], 'Min': ['minimum', 'min'],
                   'Max': ['maximum', 'max'], 'sin': ['sin'], 'cos': ['cos'], 'tan': ['tan']}
    namespace = {}
    for key, names in _CANDIDATES.items():
        for n in names:
            if hasattr(pybamm, n):
                namespace[key] = getattr(pybamm, n)
                break
    namespace.update({'ce': None, 'sto': None, 'c': None, 'T': None})
    code = compile(f'lambda {var}: {body}', '<expr>', 'eval')
    fn = eval(code, {'pybamm': pybamm, **namespace})
    # PyBaMM may call parameter functions with (concentration) or
    # (concentration, temperature) — accept any arity, use the first argument.
    def wrapper(*args):
        return fn(args[0])
    wrapper.expr_src = body
    return wrapper


def curve_to_pybamm(points, monotonic_ok=True):
    import pybamm
    import numpy as np
    xs = np.array([p[0] for p in points], float)
    ys = np.array([p[1] for p in points], float)
    order = np.argsort(xs)
    xs, ys = xs[order], ys[order]
    # Interpolant needs strictly increasing x; average duplicates.
    ux, inv = np.unique(xs, return_inverse=True)
    uy = np.zeros_like(ux)
    cnt = np.zeros_like(ux)
    np.add.at(uy, inv, ys)
    np.add.at(cnt, inv, 1)
    uy /= np.maximum(cnt, 1)
    x_lo, x_hi = float(ux[0]), float(ux[-1])

    def f(arg):
        # clamp into the digitized domain — outside data the OCP is extrapolated
        # flat (documented approximation; human sees the covered range in review)
        arg_c = pybamm.minimum(pybamm.maximum(arg, x_lo), x_hi)
        return pybamm.Interpolant(ux, uy, arg_c)
    f.data_points = int(len(ux))
    f.domain = (x_lo, x_hi)
    return f


def _fit_axis_values(pairs, log):
    """pairs [(px, data)] -> (a, b); log10 space when log."""
    import numpy as np
    px = np.array([p[0] for p in pairs], float)
    dv = np.array([math.log10(p[1]) if log else p[1] for p in pairs], float)
    a, b = np.polyfit(px, dv, 1)
    return float(a), float(b)


def trace_points_from_review(reviewed, figure_id, trace_id):
    """Recompute the calibrated data points from the review export (curves section)."""
    for f in (reviewed.get('curves') or {}).get('figures', []):
        if f.get('figure_id') != figure_id:
            continue
        for t in f.get('traces', []):
            if t.get('trace_id') != trace_id:
                continue
            cal = t.get('calibration')
            if not cal:
                return None
            if 'fit' in cal.get('x', {}) and 'fit' in cal.get('y', {}):
                fx, fy = cal['x']['fit'], cal['y']['fit']
            else:
                ax = [(p['px'][0], p['data'][0] if isinstance(p['data'], (list, tuple)) else p['data'])
                      for p in cal['x']['points']]
                ay = [(p['px'][1], p['data'][1] if isinstance(p['data'], (list, tuple)) and len(p['data']) > 1
                       else (p['data'][0] if isinstance(p['data'], (list, tuple)) else p['data']))
                      for p in cal['y']['points']]
                fx = dict(zip(('a', 'b'), _fit_axis_values(ax, cal['x'].get('log', False))))
                fy = dict(zip(('a', 'b'), _fit_axis_values(ay, cal['y'].get('log', False))))
            rows = []
            for x, y in t.get('points_norm', []):
                dx = fx['a'] * x + fx['b']
                dy = fy['a'] * y + fy['b']
                if cal['x'].get('log'):
                    dx = 10 ** dx
                if cal['y'].get('log'):
                    dy = 10 ** dy
                rows.append([dx, dy])
            rows.sort(key=lambda r: r[0])
            return rows
    return None


def apply_reviewed(values, reviewed, report):
    """Apply VERIFIED reviewed entries onto a PyBaMM ParameterValues object."""
    applied, blocked = [], []
    for p in reviewed.get('parameters', []):
        name = p.get('pybamm_name')
        status = p.get('review_status')
        raw = p.get('reviewed_value', p.get('value'))
        if not name or status != 'VERIFIED' or raw is None:
            continue
        try:
            if isinstance(raw, str) and raw.startswith('expr://sym:'):
                fn = sympy_to_pybamm(raw[len('expr://sym:'):])
                values.update({name: fn})
                applied.append({'id': p['id'], 'name': name, 'kind': 'function_expr', 'expr': fn.expr_src})
            elif isinstance(raw, str) and raw.startswith('data://curve:'):
                binding = p.get('curve_binding') or {}
                parts = raw[len('data://curve:'):].split(':')
                fig_id, tr_id = parts[0], parts[1] if len(parts) > 1 else binding.get('trace_id')
                pts = binding.get('csv_points') or trace_points_from_review(reviewed, fig_id, tr_id)
                if not pts:
                    blocked.append({'id': p['id'], 'reason': f'no calibrated points found for {fig_id}/{tr_id}'})
                    continue
                fn = curve_to_pybamm(pts)
                values.update({name: fn})
                applied.append({'id': p['id'], 'name': name, 'kind': 'curve_interpolant',
                                'points': fn.data_points, 'domain': list(fn.domain)})
            elif 'exchange-current density' in name and not isinstance(raw, str):
                # The paper's m_k is a reaction-rate COEFFICIENT
                # [A.m-2.(m3.mol-1)^1.5], not j0 itself: j0 = m_k*ce^.5*cs^.5*(csmax-cs)^.5.
                # Injecting it as a constant j0 would be scientifically wrong.
                blocked.append({'id': p['id'], 'reason': 'reaction-rate coefficient needs the j0 function shape '
                                                        '(manual implement-and-test); baseline j0 retained (HYBRID)'})
            else:
                values.update({name: float(raw)})
                applied.append({'id': p['id'], 'name': name, 'kind': 'scalar', 'value': float(raw)})
        except Exception as exc:
            blocked.append({'id': p.get('id'), 'reason': f'{type(exc).__name__}: {exc}'})
    report['overrides_applied'] = applied
    report['blocked'] = blocked
    return values


def build_model():
    import pybamm
    opts = {'thermal': 'isothermal', 'SEI': 'none', 'lithium plating': 'none',
            'loss of active material': 'none', 'particle mechanics': 'none'}
    model = pybamm.lithium_ion.DFN(options=opts)
    return model, opts


def simulate_discharge(values, c_rate=1.0, cut_voltage=3.0, t_end_s=None):
    import pybamm
    import numpy as np
    model, opts = build_model()
    sim = pybamm.Simulation(model, parameter_values=values)
    cap = values['Nominal cell capacity [A.h]']
    try:
        i_raw = values['Current function [A]']
        I = float(i_raw) if not callable(i_raw) else c_rate * cap
    except (KeyError, TypeError, ValueError):
        I = c_rate * cap
    if t_end_s is None:
        t_end_s = 3600 * cap / max(I, 1e-9) * 1.3
    t_grid = np.linspace(0, min(t_end_s, 3600 * 24), 400)
    sol = sim.solve([0, min(t_end_s, 3600 * 24)], t_interp=t_grid, solver=pybamm.CasadiSolver())
    t = sol['Time [s]'].entries
    v = sol['Terminal voltage [V]'].entries
    cap_ah = I * t / 3600.0
    return {'t': t, 'V': v, 'capacity_Ah': cap_ah, 'current_A': I,
            'voltage_cutoff_reached': bool(v[-1] <= cut_voltage + 1e-6)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reviewed', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--c-rate', type=float, default=1.0)
    ap.add_argument('--cut-voltage', type=float, default=3.0)
    ap.add_argument('--calibrate', action='store_true')
    ap.add_argument('--target', help='digitized CSV (capacity_Ah,voltage_V) to calibrate against')
    ap.add_argument('--fit', help='comma list parameter_id[:scale|log_scale]')
    ap.add_argument('--max-nfev', type=int, default=8)
    ap.add_argument('--x0-scales', help='comma scales matching --fit order; skips the coarse grid search (resume)')
    ap.add_argument('--curve-csv', help='directory to write simulated curve CSV')
    args = ap.parse_args()

    try:
        import pybamm
    except ImportError as exc:
        sys.exit(f'PyBaMM is not installed in this environment (pip install -r requirements.txt): {exc}')
    import numpy as np
    reviewed = json.loads(Path(args.reviewed).read_text(encoding='utf-8'))
    report = {'pybamm_version': pybamm.__version__, 'model': 'DFN',
              'options': {'thermal': 'isothermal', 'SEI': 'none', 'lithium plating': 'none',
                          'loss of active material': 'none', 'particle mechanics': 'none'},
              'simulation': 'NOT_REQUESTED', 'calibration': 'NOT_REQUESTED'}

    values = pybamm.ParameterValues('Chen2020')
    apply_reviewed(values, reviewed, report)
    n_missing = sum(1 for p in reviewed.get('parameters', [])
                    if p.get('review_status') != 'VERIFIED' or p.get('reviewed_value', p.get('value')) is None)
    if n_missing:
        report['hybrid_warning'] = (f'{n_missing}/{len(reviewed.get("parameters", []))} dictionary entries are '
                                    'unreviewed/missing -> filled by Chen2020 baseline. This is a HYBRID '
                                    'experiment, NOT a paper reproduction.')
    print(report.get('hybrid_warning') or 'All entries reviewed: paper-only reproduction (no baseline gap fill flagged).')

    if args.run or args.calibrate:
        c_rate = args.c_rate
        if args.calibrate:
            target_rows = read_curve_csv(args.target)
            specs = args.fit.split(',')
            names = {s.split(':')[0]: (s.split(':')[1] if ':' in s else 'scale') for s in specs}
            pid2name = {p['id']: p['pybamm_name'] for p in reviewed.get('parameters', []) if p.get('pybamm_name')}
            base = {}
            for pid in names:
                ent = next(p for p in reviewed.get('parameters', []) if p['id'] == pid)
                base[pid] = float(ent.get('reviewed_value', ent.get('value')))
            from scipy.optimize import least_squares
            cap = float(values['Nominal cell capacity [A.h]'])
            I = c_rate * cap
            tx = np.array([r[0] for r in target_rows]); ty = np.array([r[1] for r in target_rows])
            history = []
            def log(msg):
                print(msg, flush=True)

            def unpack(x):
                scales = {}
                i = 0
                for pid, mode in names.items():
                    scales[pid] = math.exp(x[i]) if mode == 'log_scale' else x[i]
                    i += 1
                return scales

            SHORTFALL_RATE = 0.1  # V per missing Ah, documented in the report

            def evaluate(x):
                """Solve once, return (scales, cost, sim, sim_cap). Cost is a
                SCALAR comparable across scales: RMSE over the overlapping
                capacity window plus the shortfall penalty — never nan."""
                scales = unpack(x)
                v2 = pybamm.ParameterValues('Chen2020')
                apply_reviewed(v2, reviewed, {})
                for pid, val in base.items():
                    v2.update({pid2name[pid]: base[pid] * scales[pid]})
                try:
                    r = simulate_discharge(v2, c_rate=c_rate, cut_voltage=args.cut_voltage)
                except Exception as exc:
                    log(f'  solve failed: {exc}')
                    return scales, 10.0, None, 0.0
                sx = r['capacity_Ah']; sy = r['V']
                interp = np.interp(tx, sx, sy, left=np.nan, right=np.nan)
                mask = ~np.isnan(interp)
                res = interp[mask] - ty[mask]
                rmse = float(np.sqrt(np.mean(res ** 2))) if len(res) else None
                shortfall = max(0.0, float(tx[-1] - sx[-1]))
                cost = (rmse if rmse is not None else 1.0) + SHORTFALL_RATE * shortfall
                history.append({'scales': {k: round(v, 4) for k, v in scales.items()},
                                'rmse_V': rmse, 'sim_capacity_Ah': float(sx[-1]),
                                'cost_V': round(cost, 4)})
                rmse_txt = f'{rmse*1000:.1f} mV' if rmse is not None else 'no overlap'
                log(f"  iter {len(history)}: scales={ {k: round(v,4) for k,v in scales.items()} } "
                    f"sim_cap={sx[-1]:.2f} Ah rmse={rmse_txt} cost={cost:.3f} V")
                return scales, cost, r, float(sx[-1])

            def residuals(x):
                """Fixed-length residual vector for scipy least_squares:
                one component per target point (missing coverage -> shortfall
                penalty, NOT dropped) plus an explicit shortfall component.
                Variable-length vectors break finite differencing."""
                scales, cost, r, sim_cap = evaluate(x)
                if r is None:
                    return np.full(len(tx) + 1, 10.0)
                sx = r['capacity_Ah']; sy = r['V']
                interp = np.interp(tx, sx, sy, left=np.nan, right=np.nan)
                shortfall = max(0.0, float(tx[-1] - sim_cap))
                fill = SHORTFALL_RATE * shortfall
                res = np.where(np.isnan(interp), fill, interp - ty)
                return np.append(res, fill)

            x0, lb, ub = [], [], []
            for pid, mode in names.items():
                if mode == 'log_scale':
                    x0.append(0.0); lb.append(math.log(0.05)); ub.append(math.log(20.0))
                else:
                    x0.append(1.0); lb.append(0.05); ub.append(20.0)
            # --- Stage A: coarse bounded coordinate search -------------------
            # Relative finite differences are degenerate at x=0 (log scale 1.0),
            # so first scan a small log-spaced grid per parameter (bounded, every
            # evaluation logged, scalar cost) and refine with scipy FROM the best.
            grid = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0]
            best = list(x0)
            best_cost = None
            if args.x0_scales:
                seeds = [float(v) for v in args.x0_scales.split(',')]
                best = [math.log(g) if mode == 'log_scale' else g
                        for g, (_, mode) in zip(seeds, names.items())]
                _, best_cost, _, _ = evaluate(np.array(best))
                log(f'  resume from --x0-scales {seeds}: cost={best_cost:.3f} V (grid search skipped)')
            for i, (pid, mode) in enumerate(names.items()) if not args.x0_scales else []:
                cand_best, cand_cost = None, None
                for g in grid:
                    x = list(best); x[i] = math.log(g) if mode == 'log_scale' else g
                    _, cost, _, _ = evaluate(np.array(x))
                    if cand_cost is None or cost < cand_cost:
                        cand_best, cand_cost = x, cost
                best, best_cost = cand_best, cand_cost
            log(f'  coarse search best: scales={ {k: round(v, 4) for k, v in unpack(best).items()} } cost={best_cost:.3f} V')
            # --- Stage B: least_squares polish from the coarse optimum -------
            from scipy.optimize import least_squares as _ls
            sol = _ls(residuals, best, bounds=(lb, ub), max_nfev=args.max_nfev, diff_step=0.1)
            scales = unpack(sol.x)
            final = {}
            for pid, mode in names.items():
                v_final = base[pid] * scales[pid]
                final[pid] = v_final
                values.update({pid2name[pid]: v_final})
            report['calibration'] = {
                'status': 'CALIBRATED', 'method': 'coarse log-grid search + bounded least_squares (scipy)',
                'target': Path(args.target).name, 'n_target_points': len(target_rows),
                'coarse_search_cost_V': best_cost,
                'fitted': [{'id': pid, 'pybamm_name': pid2name[pid], 'base': base[pid],
                            'factor': round(scales[pid], 4), 'fitted_value': final[pid],
                            'label': 'CALIBRATED_SIMULATION_FIT (never cite as paper evidence)'} for pid in names],
                'iterations': history[-6:],
            }
        # final simulation with applied/calibrated values — a failed solve must
        # still leave a FAILED report on disk (fail-closed, no silent loss)
        try:
            r = simulate_discharge(values, c_rate=c_rate, cut_voltage=args.cut_voltage)
        except Exception as exc:
            report['simulation'] = {
                'status': 'FAILED', 'c_rate': c_rate, 'cut_voltage_V': args.cut_voltage,
                'error': f'{type(exc).__name__}: {exc}',
                'label': 'HYBRID baseline fills unreviewed gaps' if n_missing else 'paper-reviewed parameters',
            }
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            print('Wrote:', args.output)
            sys.exit(3)
        report['simulation'] = {
            'status': 'SOLVED', 'c_rate': c_rate, 'current_A': r['current_A'],
            'duration_s': float(r['t'][-1]), 'capacity_Ah': float(r['capacity_Ah'][-1]),
            'final_voltage_V': float(r['V'][-1]), 'cut_voltage_V': args.cut_voltage,
            'label': 'HYBRID baseline fills unreviewed gaps' if n_missing else 'paper-reviewed parameters',
        }
        if args.curve_csv:
            out_csv = Path(args.curve_csv)
            out_csv.parent.mkdir(parents=True, exist_ok=True)
            # resample the solution onto a uniform capacity grid for plotting
            cap_grid = np.linspace(float(r['capacity_Ah'][0]), float(r['capacity_Ah'][-1]), 250)
            v_grid = np.interp(cap_grid, r['capacity_Ah'], r['V'])
            with open(out_csv, 'w', newline='') as fh:
                w = csv.writer(fh)
                w.writerow(['capacity_Ah', 'voltage_V'])
                w.writerows(zip(np.round(cap_grid, 6), np.round(v_grid, 6)))
            report['simulation']['curve_csv'] = str(out_csv)
            try:
                import matplotlib
                matplotlib.use('Agg')
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(6, 4))
                ax.plot(r['capacity_Ah'], r['V'], label=f'simulated {c_rate}C (PyBaMM DFN)')
                if args.calibrate:
                    ax.plot(tx, ty, 'k.', ms=3, label='digitized paper curve')
                ax.set_xlabel('Capacity [Ah]'); ax.set_ylabel('Voltage [V]')
                ax.set_title('P2D simulation vs digitized paper curve (review-gated)')
                ax.legend(); fig.tight_layout()
                png = out_csv.with_suffix('.png')
                fig.savefig(png, dpi=150)
                report['simulation']['curve_png'] = str(png)
            except Exception as exc:
                report['simulation']['plot_error'] = str(exc)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Wrote:', args.output)
    if report.get('simulation', {}).get('status') == 'FAILED':
        sys.exit(3)


if __name__ == '__main__':
    main()
