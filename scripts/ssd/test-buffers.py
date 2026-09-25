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
    # A freshly prepared source tree has no generated build configuration.
    # Use an isolated native-style layout without changing a developer's build.
    native = out/'native'
    (native/'src').mkdir(parents=True)
    (native/'build').mkdir()
    names = ['neo_ssd_firmware.c', 'neo_ssd_firmware.h', 'neo_ssd_services.c',
             'neo_ssd_services.h', 'neo_ssd_buffers.c', 'neo_ssd_buffers.h',
             'neo_ssd_identify.h']
    for name in names:
        shutil.copy2(m1n1/'src'/name, native/'src'/name)
    (native/'build/build_cfg.h').write_text('#define VLINUX_SSD_BUFFER_PROBE\n')
    clang = args.clang
    resource = subprocess.check_output([clang, '-print-resource-dir'], text=True).strip()
    cmd = [clang, '-ffreestanding', '-nostdinc', '-isystem', resource+'/include',
           '-isystem', str(m1n1/'sysinc'), '-I'+str(native/'src'), '-I'+str(m1n1/'src'), '-I'+str(out),
           '-O1', '-g0', '-fsanitize=address,undefined', '-U__APPLE__',
           '-U__UINT64_TYPE__', '-D__UINT64_TYPE__=unsigned long',
           '-U__INT64_TYPE__', '-D__INT64_TYPE__=long',
           str(native/'src/neo_ssd_firmware.c'), str(native/'src/neo_ssd_services.c'), str(native/'src/neo_ssd_buffers.c'), str(ROOT/'scripts/ssd/check-buffers.c'),
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
              'configuration_from_header': True,
              'build_cfg_sha256': digest(native/'build/build_cfg.h'),
              'identify_header_sha256': digest(m1n1/'src/neo_ssd_identify.h'),
              'scope': 'Actual discovery and buffer policy under ASan/UBSan. Minimal non-identifying ADT fixture, native initial request, simulated SART/mailbox/DMA buffers. No native device, cache maintenance, FDT or exception-handler execution.'}
    match = re.search(r'ALL_BUFFER_HOST_CHECKS_PASSED mmio-positions=(\d+) write-fault-cases=(\d+) protocol-cases=(\d+) poll-fault-cases=(\d+)', log)
    if match:
        result.update(zip(['mmio_positions', 'write_fault_cases', 'protocol_cases', 'poll_fault_cases'], map(int, match.groups())))
    else:
        result['passed'] = False
    stream = re.search(r'NATIVE_STREAM_FAULT_CHECKS_PASSED positions=(\d+) write-fault-cases=(\d+) replay-cases=(\d+)', log)
    if stream:
        result.update(zip(['stream_mmio_positions', 'stream_write_fault_cases', 'native_stream_cases'], map(int, stream.groups())))
    else:
        result['passed'] = False
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(log)
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
