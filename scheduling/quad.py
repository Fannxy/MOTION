#!/usr/bin/env python3
# quad_vec.py
import argparse, socket, pickle, struct, time, hashlib
import numpy as np
import asyncio

P = (1 << 61) - 1
def modp(x): return x % P

# ---- 向量版模运算 ----
def modp_vec(x): return np.array(x, dtype=np.int64) % P
def addp_vec(a,b): return (a + b) % P
def subp_vec(a,b): return (a - b) % P
def mulp_vec(a,b): return (a * b) % P

# # ---- 发送/接收对象（高效版） ----
# def send_obj(sock, obj, stats):
#     data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
#     header = struct.pack("!I", len(data))
#     sock.sendall(header + data)
#     stats["sent"] += len(header) + len(data)

# def recv_obj(sock, stats):
#     header = sock.recv(4)
#     if not header:
#         raise ConnectionError("peer closed")
#     (length,) = struct.unpack("!I", header)
#     buf = bytearray()
#     while len(buf) < length:
#         chunk = sock.recv(length - len(buf))
#         if not chunk:
#             raise ConnectionError("peer closed")
#         stats["recv"] += len(chunk)
#         buf.extend(chunk)
#     return pickle.loads(buf)

# ---- 组网 ----
def connect_all(id_, ips, port_base, timeout=120):
    N = len(ips)
    peers, stats = {}, {}
    for j in range(N):
        if j != id_:
            stats[j] = {"sent":0, "recv":0}

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((ips[id_], port_base + id_))
    server.listen(N)
    server.settimeout(1.0)

    # 连接大id
    for j in range(id_+1, N):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1<<20)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1<<20)
        deadline = time.time() + timeout
        while True:
            try:
                s.connect((ips[j], port_base + j))
                break
            except Exception:
                if time.time() > deadline:
                    raise
                time.sleep(0.2)
        send_obj(s, {"hello": id_}, stats[j])
        peers[j] = s

    # 接受小id
    need = set(range(0, id_))
    deadline = time.time() + timeout
    while need:
        if time.time() > deadline:
            raise TimeoutError("accept timeout")
        try:
            conn, _ = server.accept()
            tmpstats = {"sent":0, "recv":0}
            hello = recv_obj(conn, tmpstats)
            j = int(hello["hello"])
            stats[j] = tmpstats
            peers[j] = conn
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1<<20)
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1<<20)
            need.discard(j)
        except socket.timeout:
            pass
    server.close()
    return peers, stats

import asyncio, pickle, struct

# ---- 异步发送/接收对象 ----
async def send_obj(writer, obj, stats):
    data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    header = struct.pack("!I", len(data))
    writer.write(header + data)
    await writer.drain()
    stats["sent"] += len(header) + len(data)

async def recv_obj(reader, stats):
    header = await reader.readexactly(4)
    (length,) = struct.unpack("!I", header)
    data = await reader.readexactly(length)
    stats["recv"] += len(header) + len(data)
    return pickle.loads(data)


# ---- 异步 connect_all ----
async def async_connect_all(id_, ips, port_base, timeout=120):
    N = len(ips)
    peers, stats = {}, {}
    for j in range(N):
        if j != id_:
            stats[j] = {"sent": 0, "recv": 0}

    accepted_connections = {}

    # === 启动监听 ===
    async def handle_connection(reader, writer):
        try:
            hello = await recv_obj(reader, stats.setdefault(-1, {"sent": 0, "recv": 0}))
            j = int(hello["hello"])
            stats[j] = {"sent": 0, "recv": 0}
            accepted_connections[j] = (reader, writer)
            # 等待 main loop 把它拾取
        except Exception as e:
            print(f"[P{id_}] handler error from peer: {e}")
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_connection, ips[id_], port_base + id_)

    # === 并行发起高 id 连接 ===
    connect_tasks = []
    for j in range(id_ + 1, N):
        async def connect_to(j=j):
            deadline = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < deadline:
                try:
                    reader, writer = await asyncio.open_connection(ips[j], port_base + j)
                    await send_obj(writer, {"hello": id_}, stats[j])
                    peers[j] = (reader, writer)
                    return
                except (ConnectionRefusedError, OSError):
                    await asyncio.sleep(0.2)
            raise TimeoutError(f"[P{id_}] connect to {j} timeout")
        connect_tasks.append(asyncio.create_task(connect_to()))

    await asyncio.gather(*connect_tasks)

    # === 等待低 id 的连接 ===
    need = set(range(0, id_))
    deadline = asyncio.get_event_loop().time() + timeout
    while need and asyncio.get_event_loop().time() < deadline:
        for j in list(need):
            if j in accepted_connections:
                peers[j] = accepted_connections[j]
                need.discard(j)
        await asyncio.sleep(0.05)

    if need:
        raise TimeoutError(f"[P{id_}] accept timeout, still waiting {need}")

    server.close()
    await server.wait_closed()

    return peers, stats

# ---- 批量乘法 Online 阶段（严格对齐协议）----
def one_mult_online_vec(pid, peers, io_stats, seed, n=1024):
    # 批量随机源：不同 (label, subset) 保证相同子集得到一致的向量
    def vec_add(a,b): return [(x + y) % P for x,y in zip(a,b)]
    def vec_sub(a,b): return [(x - y) % P for x,y in zip(a,b)]
    def vec_mul(a,b):
        # Python int 不溢出，直接取模即可
        return [(x * y) % P for x,y in zip(a,b)]
    
    def sgen(label, subset):
        rng = np.random.default_rng(int.from_bytes(
            hashlib.sha256(f"{seed}|{label}|{subset}".encode()).digest(), "big") % (1<<63))
        return [int(x) % P for x in rng.integers(0, P, size=n)]

    ctr = 16
    # ---- 预处理随机量（与协议/标注子集一致）----
    # r
    m, lambda1, lambda2 = sgen(f"r|{ctr}", "m"), sgen(f"λ1|{ctr}", "l1"), sgen(f"λ2|{ctr}", "l2")
    y, lambday1, lambday2 = sgen(f"r|{ctr}", "m"), sgen(f"λ1|{ctr}", "l1"), sgen(f"λ2|{ctr}", "l2")
    lambda_star1, lambda_star2 = sgen(f"λ*_1|{ctr}", "ls1"), sgen(f"λ*_2|{ctr}", "ls2")
    lambdac_star, m03, m3, r013, lambdac1, lambdac2 = None, None, None, None, None, None
    r123 = None
    lambdac = None
    
    if pid in (0,1,3):
        r013 = sgen(f"r013|{ctr}", "013")
        lambdac1 = sgen(f"λ_c1|{ctr}", "013")
    if pid in (0,2,3):
        lambdac2 = sgen(f"λ_c2|{ctr}", "023")
    if pid in (1,2,3):
        r123 = sgen(f"r123|{ctr}", "123")
        lambdac_star = sgen(f"λ*_c|{ctr}", "123")
        
    if pid in (0, 3):
        lambdac = sgen(f"λ_c|{ctr}", "03")
        m03 = lambdac + vec_mul(lambda1, lambda2) + r013
    if pid == 3:
        m3 = vec_add(vec_sub(vec_sub(vec_mul(lambda1, vec_sub(lambda2, lambda_star2)), vec_mul(lambda2, lambda_star1)), lambdac_star), r123)
    # suppose other elements are obtained already.
    if pid == 2:
        m03 = sgen(f"m02fake", "f1")
    if pid == 0:
        m0 = sgen(f"m0fake", "f2")
        
    # online phase
    v0, v12, m1, m2, m12, v1, v2 = None, None, None, None, None, None, None
    
    if pid == 0:
        v0 = vec_add(vec_mul(m, lambda1), vec_mul(y, lambday1))
    if pid in (1,2):
        v12 = vec_mul(m, y)
    if pid == 1:
        m1 = vec_add(vec_add(vec_mul(m, lambda1), vec_mul(y, lambday1)), r013)
    if pid == 2:
        m2 = vec_sub(vec_add(vec_mul(m, lambda2), vec_mul(y, lambday2)), m03)
    if pid in (1,2):
        m12 = vec_add(v12, r123)
    if pid == 1:
        v1 = vec_sub(v12, m1)
    if pid == 2:
        v2 = vec_sub(v12, m2)

    if pid == 1:
        send_obj(peers[2], {"tag":"m1", "v": m1}, io_stats[2])
        m2 = recv_obj(peers[2], io_stats[2])["v"]
    elif pid == 2:
        m1 = recv_obj(peers[1], io_stats[1])["v"]
        send_obj(peers[1], {"tag":"m2", "v": m2}, io_stats[1])
        send_obj(peers[0], {"tag":"m12", "v": m12}, io_stats[0])
    elif pid == 0:
        m12 = recv_obj(peers[2], io_stats[2])["v"]
    
    if pid == 1:
        mc = vec_sub(v1, m2)
        mc = vec_add(mc, lambdac_star)
        return mc
    elif pid == 2:
        mc = vec_sub(v2, m1)
        mc = vec_add(mc, lambdac_star)
        return mc
    elif pid == 0:
        mc_star = vec_sub(m12, vec_add(v0, m03))
        mc_star = vec_add(mc_star, lambdac)
        return mc_star
    else:
        return [0]*n

async def one_mult_online_fake(pid, peers, io_stats, seed, n=1024):
    vec = np.full(n, 0, dtype=np.uint64)
    
    if pid == 1:
        reader2, writer2 = peers[2]
        send_task = asyncio.create_task(send_obj(writer2, {"tag": "m1", "v": vec}, io_stats[2]))
        recv_task = asyncio.create_task(recv_obj(reader2, io_stats[2]))
        _, msg = await asyncio.gather(send_task, recv_task)
        return msg["v"]

    elif pid == 2:
        reader1, writer1 = peers[1]
        reader0, writer0 = peers[0]
        recv_task = asyncio.create_task(recv_obj(reader1, io_stats[1]))
        send2_task = asyncio.create_task(send_obj(writer1, {"tag": "m2", "v": vec}, io_stats[1]))
        send12_task = asyncio.create_task(send_obj(writer0, {"tag": "m12", "v": vec}, io_stats[0]))
        msg = await recv_task
        await asyncio.gather(send2_task, send12_task)
        return msg["v"]

    elif pid == 0:
        reader2, _ = peers[2]
        msg = await recv_obj(reader2, io_stats[2])
        return msg["v"]

    else:
        return np.zeros(n, dtype=np.uint64)
    # if pid == 1:
    #     # 原协议里：P1 -> P2 发送 m1；随后从 P2 收到 m2
    #     # peers[2].send({"tag": "m1", "v": vec})
    #     send_obj(peers[2], {"tag":"m1", "v": vec}, io_stats[2])
    #     # msg = peers[2].recv()
    #     m2 = recv_obj(peers[2], io_stats[2])["v"]
    #     # m2  = msg["v"]
    #     return m2  # 返回收到的向量，便于校验/计时

    # elif pid == 2:
    #     # 原协议里：先收 m1，再回 m2，另外发 m12 给 P0
    #     # msg = peers[1].recv()
    #     m1 = recv_obj(peers[1], io_stats[1])["v"]
    #     send_obj(peers[1], {"tag":"m2", "v": vec}, io_stats[1])
    #     send_obj(peers[0], {"tag":"m12", "v": vec}, io_stats[0])
    #     return m1  # 返回收到的向量，便于校验/计时

    # elif pid == 0:
    #     # 原协议里：从 P2 收到 m12
    #     # msg  = peers[2].recv()
    #     # m12  = msg["v"]
    #     m12 = recv_obj(peers[2], io_stats[2])["v"]
    #     return m12

    # else:
    #     # 第四方（若未参与交换），返回空载
    #     return np.zeros(n, dtype=np.uint64)

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--ips", type=str, required=True)
    ap.add_argument("--port-base", type=int, default=52000)
    ap.add_argument("--seed", type=str, default="bench-seed")
    ap.add_argument("--batch", type=int, default=1024)
    ap.add_argument("--print-every", type=int, default=0)
    args = ap.parse_args()

    ips = [x.strip() for x in args.ips.split(",")]
    assert len(ips) == 4, "expect 4 parties"
    pid = args.id

    # peers, io_stats = connect_all(pid, ips, args.port_base)
    peers, io_stats = await async_connect_all(pid, ips, args.port_base)
    # print(f"[P{pid}] connected: {sorted(peers.keys())}")

    # # WARMUP
    # for k in range(args.warmup):
    #     _ = one_mult_online_vec(pid, peers, io_stats, args.seed, ctr=f"warmup-{k}", n=args.batch)

    # BENCH
    t0 = time.perf_counter()
    # mc = one_mult_online_vec(pid, peers, io_stats, args.seed, n=args.batch)
    mc = await one_mult_online_fake(pid, peers, io_stats, args.seed, n=args.batch)
    t1 = time.perf_counter()

    # 统计
    elapsed = t1 - t0
    latency_ms = elapsed * 1000.0
    sent = sum(v["sent"] for v in io_stats.values())
    recv = sum(v["recv"] for v in io_stats.values())
    # print(f"[P{pid}] batch={args.batch}, total={elapsed:.3f}s, "
    #       f"per-op={latency_ms:.3f}ms, sent={sent/1e6:.3f}MB, recv={recv/1e6:.3f}MB")

    for s in peers.values():
        try: s.close()
        except: pass

if __name__ == "__main__":
    # main()
    asyncio.run(main())
