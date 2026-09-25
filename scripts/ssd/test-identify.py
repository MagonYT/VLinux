#!/usr/bin/env python3
"""Exercise actual Identify policy with captured ADT and simulated NVMe DMA."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--buffer-pool', action='store_true', help='Test the 1 MiB service-pool reservation build')
    parser.add_argument('--m1n1-source', type=Path, default=ROOT/'src/m1n1')
    parser.add_argument('--clang', default=shutil.which('clang'))
    args=parser.parse_args()
    source_tree=args.m1n1_source.resolve()
    if not args.clang: parser.error('Clang is required')
    out=args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    source=ROOT/'tests/fixtures/neo-ssd-memory.h'
    shutil.copy2(source, out/'fixture.h')
    # Match the native build: configuration comes from build/build_cfg.h,
    # never a command-line VLINUX_SSD_BUFFER_PROBE define. Isolate the copy so
    # both configurations can be tested without changing the live build tree.
    native = out/'native'
    (native/'src').mkdir(parents=True, exist_ok=True)
    (native/'build').mkdir(exist_ok=True)
    for name in ['neo_ssd_identify.c', 'neo_ssd_identify.h']:
        shutil.copy2(source_tree/'src'/name, native/'src'/name)
    cfg = '#define VLINUX_SSD_BUFFER_PROBE\n' if args.buffer_pool else ''
    (native/'build/build_cfg.h').write_text(cfg)
    expected_size = 0x100000 if args.buffer_pool else 0x10000
    clang=args.clang
    resource=subprocess.check_output([clang,'-print-resource-dir'],text=True).strip()
    command=[clang,'-ffreestanding','-nostdinc','-isystem',resource+'/include',
        '-isystem',str(source_tree/'sysinc'),'-I'+str(native/'src'),'-I'+str(source_tree/'src'),'-I'+str(out),
        '-O1','-g0','-fsanitize=address,undefined','-U__APPLE__',
        '-U__UINT64_TYPE__','-D__UINT64_TYPE__=unsigned long',
        '-U__INT64_TYPE__','-D__INT64_TYPE__=long',
        '-DSSD_TEST_EXPECTED_DMA_SIZE='+str(expected_size),
        str(native/'src/neo_ssd_identify.c'),str(ROOT/'scripts/ssd/check-identify.c'),'-o',str(out/'identify-test')]
    subprocess.run(command,check=True)
    test=subprocess.run([str(out/'identify-test')],capture_output=True,text=True,
        env=dict(os.environ,ASAN_OPTIONS='symbolize=0:detect_leaks=0'),timeout=60)
    (out/'test.log').write_text(test.stdout+test.stderr)
    result={'passed':test.returncode==0,'exit':test.returncode,'fixture_sha256':digest(source),
        'source_sha256':digest(source_tree/'src/neo_ssd_identify.c'),
        'header_sha256':digest(source_tree/'src/neo_ssd_identify.h'),
        'console_header_sha256':digest(source_tree/'src/neo_ssd_console.h'),
        'harness_sha256':digest(ROOT/'scripts/ssd/check-identify.c'),'command':command,
        'scope':'Actual C memory/command policy under ASan/UBSan. Controller, DMA and failures simulated; no native hardware or FDT/exception-handler execution.'}
    result['arena_bytes'] = expected_size
    result['configuration_from_header'] = True
    result['build_cfg_sha256'] = digest(native/'build/build_cfg.h')
    layout = re.search(r'SSD_NATIVE_LAYOUT_CHECKS_PASSED cases=(\d+)', test.stdout)
    result['native_layout_cases'] = int(layout.group(1)) if layout else 0
    if result['native_layout_cases'] != 2: result['passed'] = False
    match=re.search(r'read-faults=(\d+) write-faults=(\d+) memory-faults=(\d+) preflight-mismatches=(\d+)',test.stdout)
    if match:
        result.update(zip(['read_fault_positions','write_fault_cases','memory_fault_positions','preflight_mismatches'],map(int,match.groups())))
    else:result['passed']=False
    console=re.search(r'SSD_CONSOLE_CHECKS_PASSED cases=(\d+)',test.stdout)
    if console: result['console_cases']=int(console.group(1))
    else: result['passed']=False
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(test.stdout+test.stderr)
    print(json.dumps(result,indent=2))
    if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
