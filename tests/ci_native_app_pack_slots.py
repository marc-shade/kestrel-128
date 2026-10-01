#!/usr/bin/env python3
"""Reject exhausted startup handle tables without losing unrelated allocations."""
import argparse
import json
from pathlib import Path
import ci_native_app_pack as startup
from native_app_pack import build


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();report=dict(passed=False,physical_hardware_io=False,cases=[])
    original=startup.fixture();packed=build(original);factory=startup.Machine
    try:
        for count,name in ((30,'no-code-handle'),(29,'no-input-handle')):
            def machine():
                result=factory()
                for _ in range(count):result.alloc(1,1,owner=16)
                return result
            startup.Machine=machine
            result=startup.run(packed,original,expected_exit=3)
            result['name']=name;report['cases'].append(result)
            print('PASS',name,flush=True)
        report['passed']=True
    finally:
        startup.Machine=factory
        args.report.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
