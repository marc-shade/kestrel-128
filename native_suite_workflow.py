"""Full desktop plus Ultimate pages and two native Claude serial lifetimes.

run_suite_workflow takes report['suite_reference']: the raw replies to the
Ultimate queries the native Ultimate app makes (model, control and network
target identities, drive inventory, drive power, network interfaces and
addresses, RTC), from which the panel expectations are built. VICE supplies
absent_reference() (no cartridge). On hardware those replies came from the
deleted legacy desktop's UCI client; the REST API (version 0.1 on the
reference machine) answers none of these queries in UCI form, so there is no
hardware source for them in this tree and no hardware entry point runs this
workflow. A hardware runner must supply an independent reference with the
same fields (see absent_reference and tests/ci_native_suite_oracles.py).
"""
from datetime import datetime
import hashlib
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

from hw_native_desktop_check import run_native_workflow
from native_capture import ROOT, wait
from native_claude_check import landing_screen,capture_frame as claude_frame
from native_vdc_check import capture_frame as vdc_frame
from native_controls_check import panel_screen
from native_controls_scene import surface as controls_surface,drive_body as graphical_drives
from hwlib import lst_symbol

sys.path.insert(0, str(ROOT/'apps/claude/host'))
import font
import petscii


def text_lines(payload, limit=144):
    raw = payload.split(b'\0', 1)[0]
    text = ''.join(chr(b).upper() if 32 <= b < 127 else '.' for b in raw[:limit])
    lines = [text[i:i+36] for i in range(0, len(text), 36)] or ['']
    if len(raw) > limit:
        if text and len(text)%36:lines[-1]+='...'
        else:lines.append('...')
    return lines


def reply_data(reply):
    return bytes.fromhex(reply['data_hex'])


def failed(reply, malformed=False):
    if malformed:
        return ['UNAVAILABLE: 09  DOS 00  LINK 00', 'INVALID REPLY; R RETRIES THE QUERY.']
    if reply.get('absent'):
        return ['UNAVAILABLE: 11  DOS 00  LINK FE', '']
    return [f"UNAVAILABLE: 11  DOS {reply['dos']:02X}  LINK 00"] + text_lines(reply['status'].encode(), 31)


def info_body(reference, target=4, *, model_limit=36):
    model, identity = reference['model'], reference[f'identity-{target}']
    return (['HARDWARE'] + (text_lines(reply_data(model)[:64], model_limit) if model['ok'] else ['UNAVAILABLE'])
            + ['', f'TARGET {target}'] + (text_lines(reply_data(identity)) if identity['ok'] else failed(identity)))


def drive_body(reference):
    reply = reference['drives']
    body = ['ULTIMATE DRIVE INVENTORY', '']
    if not reply['ok']:
        return body+failed(reply)
    data = reply_data(reply)
    if not data:
        return body+failed(reply, True)
    declared, raw = data[0], data[1:]
    received = len(raw)//3
    if (declared > 4 or len(raw)%3 or (received != declared and not (declared == 4 and received == 2))
            or any(raw[i+1] > 30 or raw[i+2] > 1 for i in range(0, len(raw), 3))):
        return body+failed(reply, True)
    if not received:
        return body+['NO DRIVE RECORDS']
    if received != declared:
        if (raw[0]>=3 or raw[3]>=3 or raw[1]<8 or raw[4]<8 or raw[1]==raw[4]):
            return body+failed(reply,True)
        for slot in (0,1):
            power=reference[f'power-{slot}']
            if not power['ok']:return body+failed(power)
            allowed=(b'on',b'on ') if raw[slot*3+2] else (b'off',)
            if reply_data(power) not in allowed:return body+failed(power,True)
        body += [f'PARTIAL REPLY: {received} OF {declared} RECORDS', '']
    for slot in range(received):
        kind, iec, power = raw[slot*3:slot*3+3]
        body.append(f'SLOT {slot+1}  TYPE {kind:02X}  IEC {iec}  '+('ON' if power else 'OFF'))
    return body+['', 'TYPES: 00=1541 01=1571 02=1581', 'OTHER TYPE CODES SHOWN AS REPORTED.']


def network_body(reference, index=0):
    reply = reference['interfaces']
    data = reply_data(reply)
    count = data[0] if reply['ok'] and len(data) == 1 else 0
    body = [f'NETWORK INTERFACES: {count}']
    if not reply['ok']:
        return body+failed(reply)
    if len(data) != 1:
        return body+failed(reply, True)
    if not count:
        return body+['NO INTERFACES AVAILABLE']
    reply = reference[f'ip-{index}']; data = reply_data(reply)
    if not reply['ok']:
        return body+failed(reply)
    if len(data) != 12:
        return body+failed(reply, True)
    addresses = ['.'.join(map(str, data[i:i+4])) for i in (0,4,8)]
    return body+[f'INTERFACE {index}', '', 'IP:      '+addresses[0], 'MASK:    '+addresses[1],
                 'GATEWAY: '+addresses[2], '', 'CONFIGURED ADDRESSES; LINK UNTESTED.']


def absent_reference():
    reply = dict(ok=False, absent=True, data_hex='', dos=0, status='')
    return {name:dict(reply) for name in ('model','identity-4','identity-3','drives','interfaces','rtc')}


def terminal_screen(typed=False):
    lines = ['KESTREL CLAUDE LINK READY','❯ ✳ ⏺','Keyboard, glyphs and return test']
    if typed:
        lines += ['KEY RECEIVED: p','ESCAPE RECEIVED']
    result = bytearray(b' '*2000)
    for row, line in enumerate(lines):
        codes = bytes(petscii.to_screen_code(char) for char in line)
        result[row*80:row*80+len(codes)] = codes
    return bytes(result)


def rtc_observation(text, reference, started, finished, key_quiet, previous=None):
    origin = datetime.strptime(reply_data(reference).decode('ascii'), '%Y/%m/%d %H:%M:%S')
    observed = datetime.strptime(text, '%Y/%m/%d %H:%M:%S')
    elapsed = (observed-origin).total_seconds()
    lower = started-reference['finished']-key_quiet-15
    upper = finished-reference['started']+15
    assert lower <= elapsed <= upper, (text, lower, elapsed, upper)
    assert previous is None or observed > previous
    return observed, elapsed, [lower,upper]


def run_suite_workflow(mon, capture, work, disk, report, save, *, bridge_factory,
                       key_quiet=4, key_poll=2, kernel_prefix='native-desktop'):
    reference = report['suite_reference']
    labels = {m[2]:int(m[1],16) for m in re.finditer(r'^al ([0-9A-Fa-f]+) \.(\S+)',
              (ROOT/'target/native-desktop/claude.lbl').read_text(), re.M)}
    # Terminal BSS may be reused by the next app. Observe its result while
    # Claude still owns the allocation, through a transport-specific observer.
    close_session=getattr(bridge_factory,'close_session',None)
    if close_session is None:
        raise RuntimeError('the full suite requires a qualified live Claude shutdown observer')
    report['suite_apps'] = suite = dict(ultimate=[], claude=[])
    def extra(*, key, screens, desktop, read):
        def panel(label, body, page=0, *, target=4):
            bitmap=read(lst_symbol('native-desktop/controls','ug_bitmap'))==b'\1'
            row=dict(label=label,body=body,page=page,bitmap=bitmap)
            oracle=lambda columns:panel_screen(columns,body,page=page,focus=page)
            if bitmap:
                graphical=body;count=0
                if page==0:graphical=info_body(reference,target,model_limit=33)
                elif page==1:graphical,count=graphical_drives(body)
                expected=controls_surface(graphical,page=page,focus=page,count=count)
                actual=b''.join(capture.capture(f'{label}-surface-{offset:04x}',address=0xc000+offset,
                    count=min(2000,9216-offset)) for offset in range(0,9216,2000))
                (work/(label+'-surface.bin')).write_bytes(actual)
                assert actual==expected,(label,'Ultimate complete bitmap')
                # Since c4647f7 the VDC mirrors this verified VIC surface (no emulator canvas here).
                vdc=vdc_frame(capture,read,None,work,label,page,surface_data=actual,image_prefix='native-desktop/controls')
                row.update(graphical_body=graphical,drive_count=count,surface_sha256=hashlib.sha256(actual).hexdigest(),vdc=vdc)
            else:screens(label,oracle)
            suite['ultimate'].append(row); save()
        key(ord('U')); panel('ultimate-info', info_body(reference))
        key(0x9d); panel('ultimate-network-identity', info_body(reference,3),target=3)
        key(ord('D')); panel('ultimate-drives', drive_body(reference),1)
        key(ord('N')); panel('ultimate-network', network_body(reference),2)
        count = reply_data(reference['interfaces'])
        if reference['interfaces']['ok'] and len(count) == 1 and count[0] > 1:
            key(0x1d); panel('ultimate-network-next', network_body(reference,1),2)
        key(ord('T'))
        rtc = reference['rtc']
        if not rtc['ok']:
            panel('ultimate-clock-unavailable', ['CARTRIDGE RTC','']+failed(rtc),3)
        else:
            previous = None
            for index in range(2):
                if index:
                    key(ord('R'))
                label = f'ultimate-clock-{index}'
                start = time.monotonic()
                # The clock page is a bitmap since c4647f7: read the RTC reply
                # the app holds (uc_data, uc_length bytes). panel() then checks
                # the whole bitmap draws exactly this text.
                symbol = lambda name: lst_symbol('native-desktop/controls', name)
                length = int.from_bytes(capture.capture(label+'-clock-length',
                    address=symbol('uc_length'),count=2),'little')
                assert length == 19, (label, 'RTC reply length', length)
                text = capture.capture(label+'-clock-text',address=symbol('uc_data'),
                    count=19).decode('ascii')
                finish = time.monotonic()
                # Native query occurs before its screen capture. Include the
                # key quiet interval and command/REST observation latency.
                observed, elapsed, bounds = rtc_observation(text,rtc,start,finish,key_quiet,previous)
                body = ['CARTRIDGE RTC','',text,'S SET TIME  R REFRESH CLOCK READING.']
                panel(label,body,3)
                suite['ultimate'][-1].update(elapsed=elapsed,elapsed_bounds=bounds,
                    reference='independent RTC reference query plus monotonic elapsed time')
                previous = observed; save()
        key(27); desktop('desktop-after-ultimate',3)

        def capture_span(label, address, count, mode=0):
            data = b''.join(capture.capture(f'{label}-{offset:04x}', mode=mode, address=address+offset,
                count=min(2000,count-offset)) for offset in range(0,count,2000))
            (work/(label+'.bin')).write_bytes(data)
            return data
        original_font = capture_span('claude-font-before', 0x3000, 4096, 1)
        original_nmi = capture_span('claude-nmi-before', 0x318, 2)
        original_gate = capture_span('claude-gate-before', 0x3d3e, 2)
        desktop_header = (ROOT/'target/native-desktop/desktop.prg').read_bytes()[2:34]
        for host_exit in (False, True):
            label = 'claude-host-exit' if host_exit else 'claude-f8'
            row = dict(label=label, passed=False, host_exit=host_exit)
            suite['claude'].append(row); save()
            if hasattr(bridge_factory, 'prepare'):
                bridge_factory.prepare(label, work, row)
            key(ord('A'))
            # Since 331a881 the launch page is graphical on both displays: the
            # 40-column panel and VIC bitmap, the landing text in the retained
            # 80-column terminal model, and the VDC mirroring the VIC bitmap.
            actual, row['landing'] = claude_frame(capture, read, labels, work, label+'-landing',
                panel=landing_screen(40), terminal_chars=landing_screen(80))
            assert read(labels['cg_vdc_owned']) == b'\1'
            row['landing']['vdc'] = vdc_frame(capture, read, None, work, label+'-landing', 0,
                surface_data=actual, image_prefix='native-desktop/claude-gui')
            key(13)
            assert read(labels['serialOwned']) == b'\1'
            assert read(0x318,2) == bytes.fromhex('f01b')
            assert read(0x3d3e,2) == labels['nmiHandler'].to_bytes(2,'little')
            proc, log = bridge_factory(label, work, row)
            save()
            try:
                def settled():
                    deadline = time.monotonic()+90
                    quiet_since = None
                    old = None
                    while time.monotonic() < deadline:
                        assert proc.poll() is None, 'diagnostic bridge exited before native session'
                        state = read(labels['_rxCount'],2)+read(labels['_rxHead'])+read(labels['_rxTail'])
                        idle = state[2] == state[3] and read(labels['_framesSeen']) != b'\0'
                        assert read(labels['_native_quit']) == b'\0'
                        if idle and state == old:
                            if quiet_since is None: quiet_since = time.monotonic()
                            if time.monotonic()-quiet_since >= 1.5: return
                        else:
                            quiet_since = None
                        old = state; time.sleep(.25)
                    raise AssertionError('native serial receive never settled')
                def mirrored(stage, expected):
                    settled()
                    with capture.batch(stage+'-mirror-request'):
                        assert read(labels['_mirrorReq']) == b'\0'
                        mon.write_mem(labels['_mirrorReq'], b'\1'); mon.resume()
                    wait(lambda:read(labels['_mirrorReq']) == b'\0', 'native foreground VDC mirror completed', 30)
                    actual = capture_span(stage+'-mirror', labels['_mirrorBuf'], 2000)
                    assert actual == expected, (stage,'terminal mismatch')
                mirrored(label+'-connected', terminal_screen())
                if not host_exit:
                    key(ord('P')); key(27)
                    mirrored(label+'-typed', terminal_screen(True))
                    before_rx = read(labels['_rxCount'],2)
                    key(0x84)
                    wait(lambda:read(labels['_rxCount'],2) != before_rx, 'HELP received new serial data', 60)
                    mirrored(label+'-help', terminal_screen(True))
                    assert capture_span(label+'-vdc',0,2000,1) == terminal_screen(True)
                    capture_span(label+'-vic',0x400,1000)
                    during = capture_span(label+'-font',0x3000,4096,1)
                    for code, bitmap in font.definitions():
                        assert during[16*code:16*code+16] == bytes(bitmap)+bytes(8)
                row['counters'] = {name:int.from_bytes(capture_span(label+name,labels[name],size),'little')
                    for name,size in (('_rxCount',2),('_nmiCount',2),('_rxDropped',1),('_rxOverruns',1))}
                assert row['counters']['_rxDropped'] == row['counters']['_rxOverruns'] == 0
                assert row['counters']['_nmiCount'] >= row['counters']['_rxCount'] >= 3+10*len(list(font.definitions()))
                outcome=close_session(mon,work,row,labels,ord('Q') if host_exit else 0x8c,report)
                assert outcome == bytes([0 if host_exit else 2])
                wait(lambda:read(0x3d60,32) == desktop_header and read(0x3d12) == b'\1',
                     'Claude returned through native dispatcher', 180)
                desktop(label+'-desktop',4)
                assert capture_span(label+'-font-after',0x3000,4096,1) == original_font
                assert capture_span(label+'-nmi-after',0x318,2) == original_nmi
                assert capture_span(label+'-gate-after',0x3d3e,2) == original_gate
                row['close_outcome'] = outcome[0]
                row['host_exit_code'] = proc.wait(timeout=25)
                assert row['host_exit_code'] == 0
                row['passed'] = True; save()
                print('Verified native serial lifetime:', label, flush=True)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(timeout=25)
                    except subprocess.TimeoutExpired: proc.kill(); proc.wait()
                row['host_process_terminal'] = proc.poll() is not None
                row['host_final_code'] = proc.returncode
                log.close(); save()

    run_native_workflow(mon,capture,work,disk,report,save,key_quiet=key_quiet,key_poll=key_poll,
                        kernel_prefix=kernel_prefix,additional_apps=extra)
    suite['passed'] = True; save()


def physical_bridge_factory(host):
    processes = []
    def start(label, work, row):
        log = (work/(label+'-bridge.log')).open('w')
        command = [sys.executable,'-B',str(ROOT/'apps/claude/run.py'),'--connect',host+':3000',
                   '--command',shlex.join([sys.executable,'-B',str(ROOT/'tests/fixtures/claude-session.py')]),
                   '--no-panel','-v']
        row['bridge_command'] = command
        try:
            proc = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            processes.append((proc,log))
            return proc, log
        except BaseException: log.close(); raise
    start.processes = processes
    return start


def close_bridges(factory):
    for proc, log in factory.processes:
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=25)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        log.close()
