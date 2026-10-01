#!/usr/bin/env python3
"""Check independent reference rendering against the native Ultimate app."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'tests')]
from ci_native_controls import Panel
from native_suite_workflow import info_body, drive_body, network_body, rtc_observation


def reply(data, ok=True, status='00,OK'):
    return dict(ok=ok, data_hex=data.hex(), status=status, dos=int(status[:2]))


def run():
    p = Panel()
    d = p.device
    ref = dict(model=reply(d.model), drives=reply(d.inventory), interfaces=reply(bytes([d.interfaces])))
    ref.update({'power-0':reply(b'on'),'power-1':reply(b'off')})
    ref.update({f'identity-{target}':reply(d.identities[target]) for target in (3,4)})
    ref.update({f'ip-{index}':reply(data) for index,data in enumerate(d.addresses)})
    p.check(info_body(ref))
    p.key(0x9d); p.check(info_body(ref,3))
    p.key(ord('D')); p.check(drive_body(ref))
    p.key(ord('N')); p.check(network_body(ref))
    p.key(0x1d); p.check(network_body(ref,1))
    d.inventory = bytes([4,0,8,1,1,9,0]); ref['drives'] = reply(d.inventory)
    p.key(ord('D')); p.check(drive_body(ref))
    d.inventory = b'\x01\x00\xff\x01'; ref['drives'] = reply(d.inventory)
    p.key(ord('R')); p.check(drive_body(ref))
    p.exit()
    cases = ['native dual-console identification, interface navigation, full/partial and malformed inventory match independent query input']

    p = Panel()
    d = p.device
    d.faults[b'\x04\x29\x01'] = [(b'',b'99,NOT IMPLEMENTED')]
    ref['drives'] = reply(b'',False,'99,NOT IMPLEMENTED')
    p.key(ord('D')); p.check(drive_body(ref))
    d.faults[b'\x03\x05\0'] = [(b'',b'99,NOT IMPLEMENTED')]
    ref['ip-0'] = reply(b'',False,'99,NOT IMPLEMENTED')
    p.key(ord('N')); p.check(network_body(ref))
    p.exit()
    cases.append('unsupported queries retain exact DOS failure status in the native panel')

    ref = reply(b'2026/09/12 23:59:58')
    ref.update(started=100.0,finished=101.0)
    observed, elapsed, bounds = rtc_observation('2026/09/13 00:00:58',ref,160,162,4)
    assert elapsed == 60 and bounds[0] <= elapsed <= bounds[1]
    for text in ('2026/09/12 23:59:58','2026/09/13 01:00:00','2026/09/31 00:00:00'):
        try: rtc_observation(text,ref,160,162,4)
        except (ValueError,AssertionError): pass
        else: raise AssertionError('stale, future or impossible RTC reading admitted')
    try: rtc_observation('2026/09/13 00:00:58',ref,160,162,4,previous=observed)
    except AssertionError: pass
    else: raise AssertionError('RTC refresh failed to advance')
    cases.append('independent RTC window handles midnight and rejects stale, future, impossible and nonadvancing readings')
    return cases


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    report=dict(passed=False,physical_hardware_io=False)
    try:
        report['cases']=run();report['passed']=True
        print('PASS:',len(report['cases']),'native suite reference groups',flush=True)
    except BaseException as error: report['error']=repr(error);raise
    finally: args.report.write_text(json.dumps(report,indent=2)+'\n')
