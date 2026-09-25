#!/usr/bin/env python3
"""Test bounded SART mappings, RTKit buffers, and every simulated access fault."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--m1n1-source', type=Path, default=ROOT / 'src/m1n1')
    parser.add_argument('--clang', default='/opt/homebrew/opt/llvm/bin/clang' if Path('/opt/homebrew/opt/llvm/bin/clang').is_file() else 'clang')
    args = parser.parse_args()
    out = args.output.resolve()
    m1n1 = args.m1n1_source.resolve()
    out.mkdir(parents=True)
    source = ROOT / 'tests/fixtures/neo-ssd.h'
    shutil.copy2(source, out/'fixture.h')
    clang = args.clang
    resource = subprocess.check_output([clang, '-print-resource-dir'], text=True).strip()
    cmd = [clang, '-DVLINUX_SSD_BUFFER_PROBE', '-ffreestanding', '-nostdinc', '-isystem', resource+'/include',
           '-isystem', str(m1n1/'sysinc'), '-I'+str(m1n1/'src'), '-I'+str(out),
           '-O1', '-g0', '-fsanitize=address,undefined', '-U__APPLE__',
           '-U__UINT64_TYPE__', '-D__UINT64_TYPE__=unsigned long',
           '-U__INT64_TYPE__', '-D__INT64_TYPE__=long',
           str(m1n1/'src/neo_ssd_firmware.c'), str(m1n1/'src/neo_ssd_services.c'), str(m1n1/'src/neo_ssd_buffers.c'), str(ROOT/'scripts/ssd/check-buffers.c'),
           '-o', str(out/'buffers-test')]
    subprocess.run(cmd, check=True)
    test = subprocess.run([str(out/'buffers-test')], capture_output=True, text=True,
                          env=dict(os.environ, ASAN_OPTIONS='symbolize=0:detect_leaks=0'), timeout=60)
    log = test.stdout + test.stderr
    (out/'test.log').write_text(log)
    result = {'passed': test.returncode == 0, 'exit': test.returncode, 'command': cmd,
              'fixture_sha256': digest(source),
              'source_sha256': digest(m1n1/'src/neo_ssd_buffers.c'),
              'service_source_sha256': digest(m1n1/'src/neo_ssd_services.c'),
              'service_header_sha256': digest(m1n1/'src/neo_ssd_services.h'),
              'discovery_source_sha256': digest(m1n1/'src/neo_ssd_firmware.c'),
              'discovery_header_sha256': digest(m1n1/'src/neo_ssd_firmware.h'),
              'header_sha256': digest(m1n1/'src/neo_ssd_buffers.h'),
              'harness_sha256': digest(ROOT/'scripts/ssd/check-buffers.c'),
              'scope': 'Actual discovery and buffer policy under ASan/UBSan. Minimal non-identifying ADT fixture, native initial request, simulated SART/mailbox/DMA buffers. No native device, cache maintenance, FDT or exception-handler execution.'}
    match = re.search(r'ALL_BUFFER_HOST_CHECKS_PASSED mmio-positions=(\d+) write-fault-cases=(\d+) protocol-cases=(\d+) poll-fault-cases=(\d+)', log)
    if match:
        result.update(zip(['mmio_positions', 'write_fault_cases', 'protocol_cases', 'poll_fault_cases'], map(int, match.groups())))
    else:
        result['passed'] = False
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(log)
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
