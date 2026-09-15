#!/usr/bin/env python3
"""Sequential native and stock-rclpy benchmark; retain complete reports."""
import argparse,json,subprocess,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',default='build/benchmark-comparison.json')
    p.add_argument('--messages',type=int,default=10000)
    p.add_argument('--size',type=int,default=1024)
    p.add_argument('--frequency',type=int,default=1000)
    p.add_argument('--load',action='store_true')
    p.add_argument('--fifo',action='store_true')
    a=p.parse_args();destination=Path(a.output).resolve();destination.parent.mkdir(parents=True,exist_ok=True)
    reports={}
    for implementation in ['native','rclpy']:
        output=destination.with_name(destination.stem+'-'+implementation+'.json')
        cmd=[sys.executable,str(Path(__file__).with_name('benchmark_dds.py')),'--output',str(output),'--implementation',implementation,'--messages',str(a.messages),'--size',str(a.size),'--frequency',str(a.frequency)]
        if a.load:cmd.append('--load')
        if a.fifo:cmd.append('--fifo')
        subprocess.run(cmd,check=True)
        reports[implementation]=json.loads(output.read_text())
    destination.write_text(json.dumps({'scope':'same-host sequential comparison; one run per implementation, not a universal speed claim','results':reports},indent=2))
    print('Implementation   p50 us     p95 us     p99 us     received')
    for name,r in reports.items():print(f"{name:14} {r['p50_latency_us']:9.2f} {r['p95_latency_us']:10.2f} {r['p99_latency_us']:10.2f} {r['received_messages']:10}")
if __name__=='__main__':main()
