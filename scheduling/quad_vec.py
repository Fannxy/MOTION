#!/usr/bin/env python3
# quad_vec.py
import argparse, socket, pickle, struct, time, hashlib
import numpy as np

P = (1 << 61) - 1
def modp(x): return x % P

# ---- 向量版模运算 ----
def modp_vec(x): return np.array(x, dtype=np.int64) % P
def addp_vec(a,b): return (a + b) % P
def subp_vec(a,b): return (a - b) % P
def mulp_vec(a,b): return (a * b) % P

# ========================= 套接字 & 流式收发 =========================
def tune_socket(sock: socket.socket, *,
                nodelay=True, keepalive=True,
                sndbuf=16*1024*1024, rcvbuf=16*1024*1024):
    if nodelay:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    if keepalive:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, 'TCP_KEEPIDLE'):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
        if hasattr(socket, 'TCP_KEEPINTVL'):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        if hasattr(socket, 'TCP_KEEPCNT'):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, sndbuf)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)

class StreamPeer:
    """
    每个对端一个实例。基于 socket.makefile 的流式 pickle，
    适合 MB~GB 级对象的稳定传输。
    """
    def __init__(self, sock: socket.socket):
        self.sock = sock
        tune_socket(self.sock)
        # 注意：不要混用 send/recv 与 makefile
        self._fw = self.sock.makefile('wb', buffering=0)
        self._fr = self.sock.makefile('rb', buffering=0)
        self._pickler = pickle.Pickler(self._fw, protocol=pickle.HIGHEST_PROTOCOL)
        self._unpickler = pickle.Unpickler(self._fr)

    def send(self, obj):
        self._pickler.dump(obj)
        self._fw.flush()

    def recv(self):
        return self._unpickler.load()

    def close(self):
        for f in (self._fw, self._fr):
            try: f.close()
            except Exception: pass
        try: self.sock.close()
        except Exception: pass

# ========================= 组网：全互连 =========================
def connect_all(id_, ips, port_base, timeout=120, sndbuf_mb=16, rcvbuf_mb=16):
    """
    id_: 本节点逻辑 id（0..N-1）
    ips: 各节点 IP 列表（顺序与 id 一致）
    port_base: 端口基数，节点 j 监听在 port_base + j
    返回：peers: {peer_id: StreamPeer}
    """
    N = len(ips)
    peers = {}

    # 监听本节点端口
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((ips[id_], port_base + id_))
    server.listen(N)
    server.settimeout(1.0)

    # 连接 id 更大的节点
    for j in range(id_ + 1, N):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tune_socket(s, sndbuf=sndbuf_mb*1024*1024, rcvbuf=rcvbuf_mb*1024*1024)
        deadline = time.time() + timeout
        while True:
            try:
                s.connect((ips[j], port_base + j))
                break
            except Exception:
                if time.time() > deadline:
                    raise TimeoutError(f"connect to {j} timed out")
                time.sleep(0.2)
        sp = StreamPeer(s)
        sp.send({"hello": id_})   # 握手：告知自身 id
        peers[j] = sp

    # 接受来自 id 更小的连接，并读 hello 确认对端 id
    need = set(range(0, id_))
    deadline = time.time() + timeout
    while need:
        if time.time() > deadline:
            server.close()
            # 关闭已连
            for sp in peers.values(): sp.close()
            raise TimeoutError("accept timeout")
        try:
            conn, _ = server.accept()
            tune_socket(conn, sndbuf=sndbuf_mb*1024*1024, rcvbuf=rcvbuf_mb*1024*1024)
            sp = StreamPeer(conn)
            hello = sp.recv()
            j = int(hello["hello"])
            if j not in need:
                sp.close()
                continue
            peers[j] = sp
            need.remove(j)
        except socket.timeout:
            pass

    server.close()
    return peers

# ========================= 批量乘法 Online 阶段（demo） =========================
def one_mult_online_vec(pid, peers, seed, n=1024):
    # 简单双端向量算子（mod P）
    def vec_add(a,b): return [(x + y) % P for x,y in zip(a,b)]
    def vec_sub(a,b): return [(x - y) % P for x,y in zip(a,b)]
    def vec_mul(a,b): return [(x * y) % P for x,y in zip(a,b)]

    # 伪随机一致生成器（不同 label/subset 组合可控复现）
    def sgen(label, subset):
        rng = np.random.default_rng(int.from_bytes(
            hashlib.sha256(f"{seed}|{label}|{subset}".encode()).digest(), "big") % (1<<63))
        return [int(x) % P for x in rng.integers(0, P, size=n)]

    ctr = 16
    # ---- 预处理随机量（示例，与你的协议一致即可）----
    m, lambda1, lambda2 = sgen(f"r|{ctr}", "m"), sgen(f"λ1|{ctr}", "l1"), sgen(f"λ2|{ctr}", "l2")
    y, lambday1, lambday2 = sgen(f"r|{ctr}", "m"), sgen(f"λ1|{ctr}", "l1"), sgen(f"λ2|{ctr}", "l2")
    lambda_star1, lambda_star2 = sgen(f"λ*_1|{ctr}", "ls1"), sgen(f"λ*_2|{ctr}", "ls2")
    r013 = lambdac1 = lambdac2 = r123 = lambdac_star = None
    lambdac = m03 = m3 = None

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
        m03 = vec_add(vec_add(lambdac, vec_mul(lambda1, lambda2)), r013 if r013 else [0]*n)
    if pid == 3:
        m3 = vec_add(vec_sub(vec_sub(vec_mul(lambda1, vec_sub(lambda2, lambda_star2)),
                                     vec_mul(lambda2, lambda_star1)),
                             lambdac_star),
                     r123)

    # online phase（示例）
    v0 = v12 = m1 = m2 = m12 = v1 = v2 = None
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

    # --- 网络交互（改为流式 send/recv） ---
    if pid == 1:
        peers[2].send({"tag":"m1", "v": m1})
        m2 = peers[2].recv()["v"]
    elif pid == 2:
        m1 = peers[1].recv()["v"]
        peers[1].send({"tag":"m2", "v": m2})
        peers[0].send({"tag":"m12", "v": m12})
    elif pid == 0:
        m12 = peers[2].recv()["v"]

    # --- 返回各方输出（示例） ---
    if pid == 1:
        mc = vec_add(vec_sub(v1, m2), lambdac_star)
        return mc
    elif pid == 2:
        mc = vec_add(vec_sub(v2, m1), lambdac_star)
        return mc
    elif pid == 0:
        mc_star = vec_add(vec_sub(m12, vec_add(v0, m03)), lambdac)
        return mc_star
    else:
        return [0]*n

# ========================= 批量乘法 Online 阶段（demo） =========================
def one_mult_online_vec_fake(pid, peers, seed, n=1024):
    # 简单双端向量算子（mod P）
    # def vec_add(a,b): return [(x + y) % P for x,y in zip(a,b)]
    # def vec_sub(a,b): return [(x - y) % P for x,y in zip(a,b)]
    # def vec_mul(a,b): return [(x * y) % P for x,y in zip(a,b)]

    # # 伪随机一致生成器（不同 label/subset 组合可控复现）
    # def sgen(label, subset):
    #     rng = np.random.default_rng(int.from_bytes(
    #         hashlib.sha256(f"{seed}|{label}|{subset}".encode()).digest(), "big") % (1<<63))
    #     return [int(x) % P for x in rng.integers(0, P, size=n)]

    # ctr = 16
    # # ---- 预处理随机量（示例，与你的协议一致即可）----
    # m, lambda1, lambda2 = sgen(f"r|{ctr}", "m"), sgen(f"λ1|{ctr}", "l1"), sgen(f"λ2|{ctr}", "l2")
    # y, lambday1, lambday2 = sgen(f"r|{ctr}", "m"), sgen(f"λ1|{ctr}", "l1"), sgen(f"λ2|{ctr}", "l2")
    # lambda_star1, lambda_star2 = sgen(f"λ*_1|{ctr}", "ls1"), sgen(f"λ*_2|{ctr}", "ls2")
    # r013 = lambdac1 = lambdac2 = r123 = lambdac_star = None
    # lambdac = m03 = m3 = None

    # if pid in (0,1,3):
    #     r013 = sgen(f"r013|{ctr}", "013")
    #     lambdac1 = sgen(f"λ_c1|{ctr}", "013")
    # if pid in (0,2,3):
    #     lambdac2 = sgen(f"λ_c2|{ctr}", "023")
    # if pid in (1,2,3):
    #     r123 = sgen(f"r123|{ctr}", "123")
    #     lambdac_star = sgen(f"λ*_c|{ctr}", "123")

    # if pid in (0, 3):
    #     lambdac = sgen(f"λ_c|{ctr}", "03")
    #     m03 = vec_add(vec_add(lambdac, vec_mul(lambda1, lambda2)), r013 if r013 else [0]*n)
    # if pid == 3:
    #     m3 = vec_add(vec_sub(vec_sub(vec_mul(lambda1, vec_sub(lambda2, lambda_star2)),
    #                                  vec_mul(lambda2, lambda_star1)),
    #                          lambdac_star),
    #                  r123)

    # # online phase（示例）
    # v0 = v12 = m1 = m2 = m12 = v1 = v2 = None
    # if pid == 0:
    #     v0 = vec_add(vec_mul(m, lambda1), vec_mul(y, lambday1))
    # if pid in (1,2):
    #     v12 = vec_mul(m, y)
    # if pid == 1:
    #     m1 = vec_add(vec_add(vec_mul(m, lambda1), vec_mul(y, lambday1)), r013)
    # if pid == 2:
    #     m2 = vec_sub(vec_add(vec_mul(m, lambda2), vec_mul(y, lambday2)), m03)
    # if pid in (1,2):
    #     m12 = vec_add(v12, r123)
    # if pid == 1:
    #     v1 = vec_sub(v12, m1)
    # if pid == 2:
    #     v2 = vec_sub(v12, m2)
    
    vec = np.full(n, 0, dtype=np.uint64)

    # --- 网络交互（改为流式 send/recv） ---
    if pid == 1:
        peers[2].send({"tag":"m1", "v": vec})
        m2 = peers[2].recv()["v"]
    elif pid == 2:
        m1 = peers[1].recv()["v"]
        peers[1].send({"tag":"m2", "v": vec})
        peers[0].send({"tag":"m12", "v": vec})
    elif pid == 0:
        m12 = peers[2].recv()["v"]

    # # --- 返回各方输出（示例） ---
    # if pid == 1:
    #     mc = vec_add(vec_sub(v1, m2), lambdac_star)
    #     return mc
    # elif pid == 2:
    #     mc = vec_add(vec_sub(v2, m1), lambdac_star)
    #     return mc
    # elif pid == 0:
    #     mc_star = vec_add(vec_sub(m12, vec_add(v0, m03)), lambdac)
    #     return mc_star
    # else:
    #     return [0]*n
    
    return vec



# ========================= 主函数 =========================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--ips", type=str, required=True)
    ap.add_argument("--port-base", type=int, default=52000)
    ap.add_argument("--seed", type=str, default="bench-seed")
    ap.add_argument("--batch", type=int, default=1024)
    args = ap.parse_args()

    ips = [x.strip() for x in args.ips.split(",")]
    assert len(ips) == 4, "expect 4 parties"
    pid = args.id

    peers = connect_all(pid, ips, args.port_base)
    print(f"[P{pid}] connected: {sorted(peers.keys())}")

    t0 = time.perf_counter()
    # mc = one_mult_online_vec(pid, peers, args.seed, n=args.batch)
    mc = one_mult_online_vec_fake(pid, peers, args.seed, n=args.batch)
    t1 = time.perf_counter()

    elapsed = t1 - t0
    print(f"[P{pid}] batch={args.batch}, total={elapsed:.3f}s, per-op={elapsed*1000.0:.3f}ms")

    for sp in peers.values():
        sp.close()

if __name__ == "__main__":
    main()