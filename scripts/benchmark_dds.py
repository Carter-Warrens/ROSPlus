#!/usr/bin/env python3
"""Measure same-host, cross-process DDS latency; does not assert hard RT."""
import argparse
import multiprocessing
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]

def cpu_load(cpu,stop,results):
    os.sched_setaffinity(0,{cpu})
    start=time.monotonic();used=time.process_time()
    while not stop.is_set():
        end=time.process_time()+.0082
        while time.process_time()<end:
            pass
        time.sleep(.0018)
    results.put({'cpu':cpu,'cpu_seconds':time.process_time()-used,'wall_seconds':time.monotonic()-start})

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--messages',type=int,default=10000)
    parser.add_argument('--size',type=int,default=1024)
    parser.add_argument('--frequency',type=int,default=1000)
    parser.add_argument('--implementation',choices=['native','rclpy'],default='native')
    parser.add_argument('--fifo',action='store_true',help='Request SCHED_FIFO for native endpoints')
    parser.add_argument('--load',action='store_true',help='Target 82% background load (at least 80% measured) on a four-core affinity set')
    args=parser.parse_args()
    workers=[];stop=multiprocessing.Event();load_results=multiprocessing.Queue()
    cores=sorted(os.sched_getaffinity(0))[:4]
    if args.load:
        os.sched_setaffinity(0,set(cores))
        for cpu in cores:
            p=multiprocessing.Process(target=cpu_load,args=(cpu,stop,load_results));p.start();workers.append(p)
    env=dict(os.environ,ROS_DOMAIN_ID='178',ROS_AUTOMATIC_DISCOVERY_RANGE='LOCALHOST')
    binary=str(ROOT/'crates/target/release/rosplus-runtime')
    adapter=os.environ.get('ROSPLUS_RCL_ADAPTER',str(ROOT/'build/librosplus_rcl.so'))
    command=[binary] if args.implementation=='native' else ['python3',str(ROOT/'scripts/stock_benchmark.py')]
    common=['--messages',str(args.messages),'--quiet']
    if args.implementation=='native':common=['--adapter',adapter]+common
    if args.fifo:common.append('--fifo')
    with tempfile.TemporaryDirectory() as directory:
        report=Path(directory)/'latency.json'
        processes=[]
        try:
            with open(Path(directory)/'output.log','w+') as log:
                sub=subprocess.Popen([*command,'dds-subscribe',*common,'--latency-report',str(report),'--timeout-seconds','30'],env=env,stdout=log,stderr=log);processes.append(sub)
                time.sleep(.3)
                pub=subprocess.Popen([*command,'dds-publish',*common,'--latency-payload','--size',str(args.size),'--frequency',str(args.frequency)],env=env,stdout=log,stderr=log);processes.append(pub)
                for p in processes:
                    p.wait(timeout=35)
                    if p.returncode!=0:log.seek(0);raise RuntimeError(log.read())
                result=json.loads(report.read_text())
                log.seek(0)
                for line in log:
                    try:
                        value=json.loads(line)
                        if value.get('event')=='publisher_summary':result['publisher']=value
                    except ValueError:pass
                result.update(implementation=args.implementation,message_size_bytes=args.size,configured_frequency_hz=args.frequency)
                if args.load:
                    stop.set()
                    for worker in workers:worker.join(timeout=2)
                    samples=[load_results.get(timeout=2) for _ in workers]
                    result['cpu_load']={'target_background_percent':82,'affinity_cpus':cores,'workers':samples,'measured_background_percent':sum(v['cpu_seconds']/v['wall_seconds'] for v in samples)/len(samples)*100}
                Path(args.output).write_text(json.dumps(result,indent=2))
                print(json.dumps(result),flush=True)
        finally:
            stop.set()
            for worker in workers:
                worker.join(timeout=2)
                if worker.is_alive():worker.kill();worker.join()
            for p in processes:
                if p.poll() is None:p.terminate()
            for p in processes:
                try:p.wait(timeout=2)
                except subprocess.TimeoutExpired:p.kill();p.wait()
if __name__=='__main__':main()
