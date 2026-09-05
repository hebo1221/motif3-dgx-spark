"""Run one local document task and shut down its owned local model server afterwards."""
import argparse
import json
import os
from pathlib import Path
import signal
import time
import campaign_support as support
from agent import run_agent

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--documents',type=Path,required=True)
    p.add_argument('--task',required=True)
    p.add_argument('--subject',action='append')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--draft',type=int,choices=[0,1],default=0)
    p.add_argument('--print-command',action='store_true')
    args=p.parse_args()
    root=Path(__file__).resolve().parent
    config=json.loads(args.config.read_text())
    backend=config.get('backend','motif')
    if backend=='motif':
        binding=support.verify_binding(config['binding'])
        for key in ('target','sidecar'):
            if Path(config[key]).resolve()!=Path(binding[key]['path']).resolve():
                raise ValueError('Model path differs from integrity binding: '+key)
    elif backend=='qwen':
        if args.draft:raise ValueError('The Motif draft sidecar cannot be used with Qwen')
        binding=json.loads(Path(config['binding']).read_text())
        identity=support.stat_file(config['target'])
        if any(binding.get(key)!=value for key,value in identity.items()):
            raise ValueError('Qwen file identity differs from its full-hash receipt')
        if binding.get('sha256')!='408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6':
            raise ValueError('Qwen binding does not match the tested official artifact')
    else:raise ValueError('Unknown backend')
    if not config.get('gpu_uuid'):
        config['gpu_uuid']=support.gpu_snapshot()['gpu'].split(',')[1].strip()
    config.setdefault('port',8825);config.setdefault('ctx_size',22016)
    config['template']=str(root/('motif3-agent.jinja' if backend=='motif' else 'qwen3-agent.jinja'))
    command=support.command_for(config,{'runtime':'integrated','draft':args.draft})
    os.environ['LD_LIBRARY_PATH']=str(Path(config['integrated_binary']).resolve().parent)
    if args.print_command:
        print(json.dumps({'command':command,'library_path':os.environ['LD_LIBRARY_PATH']},indent=2));return
    args.output.mkdir(parents=True,exist_ok=False)
    def interrupted(signum,frame):raise KeyboardInterrupt('Signal '+str(signum))
    signal.signal(signal.SIGTERM,interrupted)
    receipt={'status':'starting','backend':backend,'runtime':support.binary_receipt(config['integrated_binary'])}
    start=time.monotonic()
    try:
        with support.server(command,args.output,config['port'],config['gpu_uuid'],600) as lifecycle:
            receipt['server']=lifecycle
            receipt['task']=run_agent(args.task,args.documents,'http://127.0.0.1:'+str(config['port']),model_name='motif3' if backend=='motif' else 'qwen3-8b',subject=args.subject)
            receipt['status']=receipt['task']['status']
    except BaseException as exc:
        receipt.update(status='failed',error=repr(exc));raise
    finally:
        receipt['elapsed_including_startup_seconds']=time.monotonic()-start
        support.write_json(args.output/'receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'report':receipt['task'].get('report'),'error':receipt['task'].get('error')},ensure_ascii=False))

if __name__=='__main__':main()
