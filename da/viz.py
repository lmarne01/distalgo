from . import common, sim, transport
from pprint import pprint
from .common import ObjectLoader
import json
import os
import re
import argparse
from glob import glob
import sys

mid = 0

import da
import os
from glob import glob

# da.common.initialize_runtime_options()
# da.common.GlobalOptions['no_log'] = None
# da.common.GlobalOptions['logfile'] = None
# da.common.GlobalOptions['logconsolelevel'] = 'info'


def dump_recv_item(stream, d):
    global mid
    delay, item = stream.load()
    if isinstance(item, common.QueueEmpty):
        pass
    #         print("-- {!r} ".format(item), end='')
    else:
        if not 'messages' in d:
            d['messages'] = []
        msg = {}

        msgtype = item[1][0].value

        if msgtype == 20:
            msg['id'] = mid
            msg['sender'] = str(item[0])
            msg['clock'] = item[1][1][0]
            msg['payload'] = str(item[1][1][1])

            mid += 1

            d['messages'].append(msg)


def dump_send_item(stream, d):
    event, value = stream.load()
    # print(event, value)


def dump_trace(p):
    d = {}
    with open(p, 'rb') as stream:
        # print('Dumping {}:'.format(p))
        header = stream.read(4)
        if header != sim.TRACE_HEADER:
            sys.exit('{} is not a DistAlgo trace file!'.format(p))
        version = stream.read(4)
        #             print("\n  Generated by DistAlgo version ", end='')
        #             if version[-1] == 0:
        #                 print("{}.{}.{}".format(*version[:-1]))
        #             else:
        #                 print("{}.{}.{}-{}".format(*version))
        tracetyp = stream.read(1)[0]
        if tracetyp == sim.TRACE_TYPE_RECV:
            #                 print("  Receive trace ")
            dump_item = dump_recv_item
        elif tracetyp == sim.TRACE_TYPE_SEND:
            #                 print("  Send trace ")
            dump_item = dump_send_item
        else:
            sys.exit("Error: unknown trace type {}".format(tracetyp))

        loader = ObjectLoader(stream)
        pid = loader.load()
        parent = loader.load()
        d['process'] = str(pid)
        d['parent'] = str(parent)
        # print("  Running process: {}\tParent process: {}\n".format(pid, parent))
        while True:
            try:
                dump_item(loader, d)
            except EOFError:
                break
            except Exception as e:
                sys.exit("Error: trace file corrupted: {}\n".format(e))
        #                 return
        #             print("END OF TRACE")

        return d


def dump_spec(trace_dir):
    # exclude
    def not_in_pattern(x):
        return (not x.startswith(trace_dir + 'Node_'))

    trace_files = [x for x in glob(trace_dir + '*.trace') if not_in_pattern(x)]

    dump = []
    for f in trace_files:
        dump.append(dump_trace(f))

    return dump


def build_clocks(trace_dir):
    process_idx = 1
    pid_map = {}
    process_map = {}
    results = []

    data = dump_spec(trace_dir)
    process_count = len(data)
    process_info_map = {}
    results = {}
    for obj in data:
        process_map[obj['process']] = []
        pid_map[obj['process']] = process_idx
        m = re.match(r'<([^\:]+)\:([^\>]+)\>', obj['process'], re.M | re.I)
        process_info_map[process_idx] = [m.group(1), m.group(2), obj['process']]
        process_idx += 1

    results['process_count'] = process_count
    results['process_map'] = process_info_map
    results['pid_map'] = pid_map
    results['messages'] = []
    results['maxClock'] = 0

    for obj in data:
        for msg in obj['messages']:
            if not msg['sender'].startswith('<Node_'):
                process_map[msg['sender']].append(msg['clock'])

    for p in data:
        rcv_clk = 0
        for msg in p['messages']:
            if msg['sender'].startswith('<Node_'):
                continue

            while rcv_clk in process_map[p['process']]:
                rcv_clk += 1

            dtuple = (msg['sender'], msg['clock'])

            clk = {}
            clk[msg['sender']] = msg['clock']
            rcv_candidate = max(rcv_clk, msg['clock'] + 1)

            while rcv_candidate in process_map[p['process']]:
                rcv_candidate += 1

            clk[p['process']] = rcv_candidate

            results['messages'].append({
                'msg': msg['payload'],
                'sender': [pid_map[msg['sender']], msg['clock']],
                'receiver': [pid_map[p['process']], rcv_candidate]
            })

            results['maxClock'] = max(results['maxClock'], rcv_candidate, )
    return results


def trace_to_clocks_and_state(trace_dir):
    data = build_clocks(trace_dir)

    js = "GetVizData(" + json.dumps(data,indent=2) + ");"

    return js

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", help="Path to spec")
    parser.add_argument("--trace", help="Path to traces directory")
    parser.add_argument("--output", help="output file")
    parser.add_argument("--no-state", dest='state', action='store_false')
    parser.set_defaults(state=True)
    args = parser.parse_args()

    # todo - check spec_path is a file
    # todo - check traces_path is a directory

    spec_dir = os.path.dirname(os.path.abspath(args.spec))
    trace_dir = args.trace

    sys.path.append(spec_dir)
    result = trace_to_clocks_and_state(trace_dir, args.state, args.output)
