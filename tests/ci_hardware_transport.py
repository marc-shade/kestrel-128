#!/usr/bin/env python3
"""Prove that hardware requests retry connection setup but never sent writes."""
import argparse
from contextlib import redirect_stdout,redirect_stderr
import hashlib
import http.client
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import hw_ultimate_check
from hw_ultimate_check import ConnectingUltimate


class Connection:
    def __init__(self,*,connect_error=None,send_error=None,response_error=None,read_error=None,status=200):
        self.connect_error=connect_error;self.send_error=send_error
        self.response_error=response_error;self.read_error=read_error;self.status=status
        self.connects=0;self.closed=0;self.requests=[];self.auto_open=1

    def connect(self):
        self.connects+=1
        if self.connect_error:raise self.connect_error

    def close(self):self.closed+=1

    def request(self,method,path,body=None,headers=None):
        assert self.connects==1 and not self.auto_open
        self.requests.append(dict(method=method,path=path,body=body,headers=headers))
        if self.send_error:raise self.send_error

    def getresponse(self):
        if self.response_error:raise self.response_error
        return self

    def read(self):
        if self.read_error:raise self.read_error
        return b'{}'


def exercise(connections,operation,expected_error=None):
    ultimate=ConnectingUltimate(host='reference.invalid',timeout=60)
    with patch('hw_ultimate_check.http.client.HTTPConnection',side_effect=connections) as factory, \
         patch('hw_ultimate_check.time.sleep'),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
        try:result=operation(ultimate)
        except RuntimeError as error:
            assert expected_error and expected_error in str(error),error
        else:assert expected_error is None
    assert factory.call_count==len(connections)
    assert all(connection.connects==connection.closed==1 for connection in connections)
    return ultimate


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=dict(passed=False,cases={},hardware_io=False)
    payload=b'\0\x80\xff';address=0x3f80
    operation=lambda ultimate:ultimate.write_mem(address,payload)
    try:
        first=Connection(connect_error=TimeoutError('connect timeout'));second=Connection()
        ultimate=exercise([first,second],operation)
        assert not first.requests and len(second.requests)==1
        assert second.requests[0]==dict(method='PUT',path='/v1/machine:writemem?address=3F80&data=0080FF',
            body=None,headers={'Connection':'close'})
        assert len(ultimate.connect_failures)==1 and not ultimate.connect_failures[0]['request_sent']
        assert not ultimate.uncertain_writes
        report['cases']['connect-timeout-then-one-send']=True

        connections=[Connection(connect_error=TimeoutError('connect timeout')) for _ in range(3)]
        ultimate=exercise(connections,operation,'no request sent')
        assert not any(connection.requests for connection in connections)
        assert len(ultimate.connect_failures)==3 and not any(item['request_sent'] for item in ultimate.connect_failures)
        assert not ultimate.uncertain_writes
        report['cases']['three-connect-failures-no-send']=True

        for label,options in (
                ('send-timeout',dict(send_error=TimeoutError('send timeout'))),
                ('response-timeout',dict(response_error=TimeoutError('response timeout'))),
                ('response-disconnect',dict(response_error=http.client.RemoteDisconnected('closed'))),
                ('partial-response',dict(read_error=http.client.IncompleteRead(b'{',1))),
                ('http-error',dict(status=503))):
            connection=Connection(**options)
            ultimate=exercise([connection],operation,'acceptance unknown; not replayed')
            assert len(connection.requests)==1 and not ultimate.connect_failures
            assert ultimate.uncertain_writes==[dict(address=address,bytes=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(),replayed=False)]
            report['cases'][label+'-not-replayed']=True

        connection=Connection()
        ultimate=exercise([connection],lambda client:client._call('POST','/v1/test',payload))
        assert connection.requests==[dict(method='POST',path='/v1/test',body=payload,
            headers={'Connection':'close','Content-Type':'application/octet-stream'})]
        assert not ultimate.connect_failures and not ultimate.uncertain_writes
        report['cases']['binary-body-preserved']=True

        # No built-in address: --host or KESTREL_ULTIMATE_HOST, else a clear stop.
        with patch.object(hw_ultimate_check,'DEFAULT_HOST',None):
            try:ConnectingUltimate(timeout=60)
            except SystemExit as error:assert 'KESTREL_ULTIMATE_HOST' in str(error) and '--host' in str(error)
            else:raise AssertionError('a client started without an Ultimate address')
        with patch.object(hw_ultimate_check,'DEFAULT_HOST','ultimate.invalid'):
            assert ConnectingUltimate(timeout=60).host=='ultimate.invalid'
            assert ConnectingUltimate('explicit.invalid',timeout=60).host=='explicit.invalid'
        report['cases']['host-required-from-argument-or-environment']=True
        report['passed']=True
    finally:
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(report["cases"])} host transport cases; no hardware I/O')


if __name__=='__main__':main()
