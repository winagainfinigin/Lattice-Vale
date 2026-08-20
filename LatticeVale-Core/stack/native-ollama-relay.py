#!/usr/bin/env python3
import argparse
import asyncio
import ipaddress
import signal
import sys
import time
from collections import defaultdict


def parse_args():
    p = argparse.ArgumentParser(description='LatticeVale WSL-local TCP relay for native Windows Ollama')
    p.add_argument('--listen-address', required=True)
    p.add_argument('--listen-port', type=int, required=True)
    p.add_argument('--target-address', required=True)
    p.add_argument('--target-port', type=int, required=True)
    p.add_argument('--allow-private-target', action='store_true', help='allow only a private non-loopback IPv4 target verified by the WSL host transport')
    p.add_argument('--max-connections', type=int, default=64)
    p.add_argument('--connect-timeout', type=float, default=5.0)
    p.add_argument('--idle-timeout', type=float, default=300.0)
    return p.parse_args()


def log(message):
    stamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    print(f'{stamp} {message}', file=sys.stderr, flush=True)


_last_log = defaultdict(float)


def log_limited(key, message, every=30.0):
    now = time.monotonic()
    if now - _last_log[key] >= every:
        _last_log[key] = now
        log(message)


def validate(args):
    if not 1 <= args.listen_port <= 65535 or not 1 <= args.target_port <= 65535:
        raise SystemExit('relay ports must be 1-65535')
    if not 1 <= args.max_connections <= 1024:
        raise SystemExit('max connections must be 1-1024')
    if not 0.5 <= args.connect_timeout <= 60:
        raise SystemExit('connect timeout must be 0.5-60 seconds')
    if not 10 <= args.idle_timeout <= 86400:
        raise SystemExit('idle timeout must be 10-86400 seconds')
    try:
        listen_ip = ipaddress.ip_address(args.listen_address)
    except ValueError as exc:
        raise SystemExit(f'invalid relay listen address: {exc}')
    if listen_ip.version != 4 or listen_ip.is_loopback or listen_ip.is_unspecified or listen_ip.is_link_local:
        raise SystemExit('relay listen address must be a specific non-loopback IPv4 owned by the WSL host')
    target = args.target_address.strip().lower()
    if target == 'localhost':
        target = '127.0.0.1'
    try:
        target_ip = ipaddress.ip_address(target)
    except ValueError as exc:
        raise SystemExit(f'invalid relay target address: {exc}')
    if args.allow_private_target:
        if target_ip.version != 4 or target_ip.is_loopback or target_ip.is_unspecified or target_ip.is_link_local or target_ip.is_multicast or not target_ip.is_private:
            raise SystemExit('private relay target must be a specific private non-loopback IPv4 address')
    elif target_ip.version != 4 or not target_ip.is_loopback:
        raise SystemExit('relay target must remain on IPv4 loopback unless the verified WSL-host fallback explicitly enables a private target')
    return str(listen_ip), str(target_ip)


async def close_writer(writer):
    if writer is None:
        return
    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass


async def pipe(reader, writer, activity):
    while True:
        data = await reader.read(65536)
        if not data:
            break
        activity[0] = time.monotonic()
        writer.write(data)
        await writer.drain()


async def idle_watch(activity, idle_timeout):
    while True:
        remaining = idle_timeout - (time.monotonic() - activity[0])
        if remaining <= 0:
            return
        await asyncio.sleep(min(remaining, 5.0))


async def handle(client_reader, client_writer, target_address, target_port, connect_timeout, idle_timeout, limiter):
    peer = client_writer.get_extra_info('peername')
    if limiter.locked():
        log_limited('capacity', 'connection rejected: relay concurrency limit reached')
    try:
        await asyncio.wait_for(limiter.acquire(), timeout=0.05)
    except asyncio.TimeoutError:
        await close_writer(client_writer)
        return

    upstream_writer = None
    tasks = []
    try:
        upstream_reader, upstream_writer = await asyncio.wait_for(
            asyncio.open_connection(target_address, target_port), timeout=connect_timeout
        )
        activity = [time.monotonic()]
        traffic_tasks = [
            asyncio.create_task(pipe(client_reader, upstream_writer, activity)),
            asyncio.create_task(pipe(upstream_reader, client_writer, activity)),
        ]
        idle_task = asyncio.create_task(idle_watch(activity, idle_timeout))
        tasks = traffic_tasks + [idle_task]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        if idle_task in done:
            log_limited('idle', f'idle relay connection closed after {idle_timeout:.0f}s without traffic')
        for task in pending:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.TimeoutError:
        log_limited('connect-timeout', f'upstream connect timed out: {target_address}:{target_port}')
    except (ConnectionError, OSError) as exc:
        log_limited('upstream-error', f'upstream connection failed: {target_address}:{target_port}: {exc}')
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log_limited('unexpected', f'unexpected relay error for peer {peer}: {type(exc).__name__}: {exc}')
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await close_writer(upstream_writer)
        await close_writer(client_writer)
        limiter.release()


async def main():
    args = parse_args()
    listen_address, target_address = validate(args)
    limiter = asyncio.Semaphore(args.max_connections)
    server = await asyncio.start_server(
        lambda r, w: handle(r, w, target_address, args.target_port, args.connect_timeout, args.idle_timeout, limiter),
        listen_address,
        args.listen_port,
        backlog=min(max(args.max_connections * 2, 32), 256),
    )
    log(
        f'relay started listen={listen_address}:{args.listen_port} '
        f'target={target_address}:{args.target_port} max_connections={args.max_connections} '
        f'connect_timeout={args.connect_timeout:.1f}s idle_timeout={args.idle_timeout:.1f}s'
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    async with server:
        await stop.wait()
    log('relay stopping')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
