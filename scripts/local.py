"""Run and supervise local development servers without sourcing .env as shell code."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
env = {**os.environ, **{k: v for k, v in dotenv_values(ROOT / '.env').items() if v is not None}}
children = []

def run(args, cwd=ROOT):
    subprocess.run(args, cwd=cwd, env=env, check=True)

def shutdown(*_):
    raise KeyboardInterrupt

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)
try:
    front_port = int(env.get('FRONTEND_PORT', '3100'))
    back_port = int(env.get('BACKEND_PORT', '3200'))
    if front_port == back_port:
        raise ValueError('FRONTEND_PORT and BACKEND_PORT must differ')
    for port in (front_port, back_port):
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
            except OSError:
                raise RuntimeError(f'Port {port} is busy. Stop the previous servers or change .env.')
    mode = env.get('LOCAL_DB_MODE', 'docker')
    if mode == 'docker':
        run(['docker', 'compose', 'up', '-d', '--wait', '--wait-timeout', '180', 'mysql'])
        env['DB_HOST'] = '127.0.0.1'
        env['DB_PORT'] = env.get('MYSQL_PORT', '3307')
    elif mode != 'external':
        raise ValueError('LOCAL_DB_MODE must be docker or external')
    run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], ROOT / 'backend')
    env['API_INTERNAL_URL'] = f'http://127.0.0.1:{back_port}'
    env['NEXT_TELEMETRY_DISABLED'] = '1'
    commands = [
        ([sys.executable, '-m', 'uvicorn', 'app.main:app', '--reload', '--host', '127.0.0.1', '--port', str(back_port)], ROOT / 'backend'),
        (['npm', 'run', 'dev', '--', '--port', str(front_port)], ROOT / 'frontend'),
    ]
    for command, cwd in commands:
        children.append(subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True))
    print(f'Frontend: http://localhost:{front_port}\nAPI docs: http://localhost:{back_port}/docs\nCtrl+C stops both servers. MySQL data is retained.', flush=True)
    while all(child.poll() is None for child in children):
        time.sleep(.5)
    raise RuntimeError('A development server exited; stopping its companion.')
except KeyboardInterrupt:
    pass
except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
    print(f'Error: {exc}', file=sys.stderr)
    sys.exit(1)
finally:
    for child in children:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for child in children:
        try:
            child.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
