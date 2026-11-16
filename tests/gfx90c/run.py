#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Time the GT 1030 corpus on the NAS iGPU (gfx90c, Vega 8 in a Ryzen 7 5825U)
and fit ucas costs.  The corpus maths, the interleaved runs and the fit are
tests/gt1030/run.py's, imported; only the transport changes: snx-shaderperf runs
inside the llama-swap Docker container on the NAS, driven over ssh.  The shaders
are pushed to /tmp/lb/cal/spv in the container once before the run.
"""
import argparse, importlib.util, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SSH = "sshpass -p crocodil0 ssh -o StrictHostKeyChecking=no andrew@10.42.0.2"
WRAP = "/var/ucas-cal/spwrap.sh"   # NAS host: docker exec llama-swap snx-shaderperf, maps spv/ paths


def gt_module():
    path = os.path.join(HERE, '..', 'gt1030', 'run.py')
    spec = importlib.util.spec_from_file_location('gt1030_run', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def nas_run(cmd, log):
    """gt.run_sp's twin: the first argument is replaced by the NAS wrapper."""
    argv = ' '.join("'" + a.replace("'", "'\\''") + "'" for a in cmd[1:])
    full = '%s %s %s' % (SSH, WRAP, argv)
    with open(log, 'w') as fh:
        fh.write(full + '\n')
        fh.flush()
    p = subprocess.run(full, shell=True, stdout=subprocess.PIPE,
                       stderr=fh, text=True, cwd=HERE)
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
    ap.add_argument('--model-name', default='gfx90c')
    args = ap.parse_args()
    args.sp = WRAP
    args.no_latency = True

    gt = gt_module()
    gt.run_sp = nas_run
    man = json.load(open(os.path.join(HERE, 'manifest.json')))
    man['device'] = 'AMD Radeon Vega 8 (Ryzen 7 5825U, RADV RENOIR, gfx90c)'
    res = gt.run_all(args, man)
    costs = gt.fit(man, res)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, 'results.json'), 'w') as fh:
        json.dump(res, fh, indent=1)
    body = gt.model_text(costs).replace('model gt1030_measured', 'model ' + args.model_name)
    body = body.replace('# measured on the GT 1030 by tests/gt1030/run.py',
                        '# measured on the AMD Vega 8 iGPU (gfx90c) by tests/gfx90c/run.py')
    with open(os.path.join(args.out, 'gfx90c.model.ucas'), 'w') as fh:
        fh.write(body)
    print(body)
    sys.stdout.flush()
    gt.report(man, res, costs, args.out)


if __name__ == '__main__':
    main()
