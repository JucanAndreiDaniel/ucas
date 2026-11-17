#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Time the GT 1030 corpus on the host AMD iGPU (gp107, Vega 8 in a Ryzen 5 3550H)
and fit ucas costs.  The corpus maths, the interleaved runs and the fit are
tests/gt1030/run.py's, imported; only the transport changes: the local
snx-shaderperf is asked for the AMD device by name.
"""
import argparse, importlib.util, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = '/home/andrew/Code/ScarletNX/build/snx-shaderperf'
DEVICE = 'GTX 1050'


def gt_module():
    path = os.path.join(HERE, '..', 'gt1030', 'run.py')
    spec = importlib.util.spec_from_file_location('gt1030_run', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def local_run(cmd, log):
    """gt.run_sp's twin: force the AMD device into the tool invocation."""
    i = cmd.index(TOOL) if TOOL in cmd else 0
    cmd = list(cmd)
    cmd.insert(i + 1, '--device')
    cmd.insert(i + 2, DEVICE)
    with open(log, 'w') as fh:
        fh.write(' '.join(cmd) + '\n')
        fh.flush()
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=fh, text=True, cwd=HERE)
    if p.returncode:
        return None
    i = p.stdout.find('{')
    return json.loads(p.stdout[i:]) if i >= 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--only', default=None)
    ap.add_argument('--runs', type=int, default=20)
    ap.add_argument('--tries', type=int, default=3)
    ap.add_argument('--max-rel-err', type=float, default=0.03)
    ap.add_argument('--no-latency', action='store_true')
    ap.add_argument('--model-name', default='gp107')
    args = ap.parse_args()
    args.sp = TOOL
    args.no_latency = True  # KHR_shader_clock SM-clock path is NVIDIA-specific

    gt = gt_module()
    gt.run_sp = local_run
    man = json.load(open(os.path.join(HERE, 'manifest.json')))
    man['device'] = 'NVIDIA GTX 1050 3 GB (GP107, Pascal sm_61)'
    res = gt.run_all(args, man)
    costs = gt.fit(man, res)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, 'results.json'), 'w') as fh:
        json.dump(res, fh, indent=1)
    body = gt.model_text(costs).replace('model gt1030_measured', 'model ' + args.model_name)
    body = body.replace('# measured on the GT 1030 by tests/gt1030/run.py',
                        '# measured on the NVIDIA GTX 1050 (gp107) by tests/gp107/run.py')
    with open(os.path.join(args.out, 'gp107.model.ucas'), 'w') as fh:
        fh.write(body)
    print(body)
    sys.stdout.flush()
    gt.report(man, res, costs, args.out)


if __name__ == '__main__':
    main()
