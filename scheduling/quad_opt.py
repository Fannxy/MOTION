#!/usr/bin/env python3
# quad_vec_fast.py
import argparse, socket, pickle, time, hashlib
import numpy as np

# ========================= 有限域 F_p（p=2^61-1，Mersenne） =========================
P   = np.uint64((1 << 61) - 1)
M31 = np.uint64((1 << 31) - 1)

def mod_fold(x: np.ndarray) -> np.ndarray:
    x = (x & P) + (x >> np.uint64(61))
    x = (x & P) + (x >> np.uint64(61))
    return x - (P * (x >= P))

def addp_vec(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return mod_fold(a + b)

def subp_vec(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return mod_fold(a + (P - b))

def mulp_vec(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a0, a1 = (a & M31), (a >> np.uint64(31))
    b0, b1 = (b & M31), (b >> np.uint64(31))
    t0 = a0 * b0
    t1 = a1 * b0 + a0 * b1
    t2 = a1 * b1
    t1_low  =  t1 & np.uint64((1 << 30) - 1)
    t1_high =  t1 >> np.uint64(30)
    res = t0
    res += (t1_low << np.uint64(31))
    res += t1_high
    res += (t2 << np.uint64(1))   # 2*t2
    return mod_fold(res)

def to_field(x_like, copy=True) -> np.ndarray:
    return mod_fold(np.array(x_like, dtype=np.uint64, copy=copy))

# ========================= 轻量确定性 PRNG（SplitMix64 + PCG64） =========================
def splitmix64(x: np.uint64) -> np.uint64:
    z = (x + np.uint64(0x9E3779B97F4A7C15)) & np.uint64(0xFFFFFFFFFFFFFFFF)
    z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9); z &= np.uint64(0xFFFFFFFFFFFFFFFF)
    z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB); z &= np.uint64(0xFFFFFFFFFFFFFFFF)
    return z ^ (z >> np.uint64(31))

def seed64_from(label: str) -> np.uint64:
    h = hashlib.blake2b(label.encode(), digest_size=8).digest()
    return np.uint64(int.from_bytes(h, 'big'))

def sgen(seed_prefix: str, label: str, subset: str, n: int) -> np.ndarray:
    s = seed64_from(f"{seed_prefix}|{label}|{subset}")
    s = splitmix64(s)
    rng = np.random.Generator(np.random.PCG64(int(s)))
    return rng.integers(0, int(P), size=n, dtype=np.uint64)

# ========================= 套接字调优 & 流式收发（pickle 流） =========================
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
    def __init__(self, sock: socket.socket):
        self.sock = sock
        tune_socket(self.sock)
        self._fw = self.sock.makefile('wb', buffering=0)
        self._fr = self.sock.makefile('rb', buffering=0)
        self._pickler   = pickle.Pickler(self._fw, protocol=pickle.HIGHEST_PROTOCOL)
        self._unpickler = pickle.Unpickler(self._fr)
    def send(self, obj):
        self._pickler.dump(obj); self._fw.flush()
    def recv(self):
        return self._unpickler.load()
    def close(self):
        for f in (self._fw, self._fr):
            try: f.close()
            except Exception: pass
        try: self.sock.close()
        except Exception: pass

# ========================= 组网（完全图：连接更大 id，接受更小 id） =========================
def connect_all(id_, ips, port_base, timeout=120, sndbuf_mb=16, rcvbuf_mb=16):
    N = len(ips)
    peers = {}
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((ips[id_], port_base + id_))
    server.listen(N)
    server.settimeout(1.0)

    for j in range(id_ + 1, N):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tune_socket(s, sndbuf=sndbuf_mb*1024*1024, rcvbuf=rcvbuf_mb*1024*1024)
        deadline = time.time() + timeout
        while True:
            try:
                s.connect((ips[j], port_base + j)); break
            except Exception:
                if time.time() > deadline:
                    raise TimeoutError(f"connect to {j} timed out")
                time.sleep(0.2)
        sp = StreamPeer(s)
        sp.send({"hello": id_})
        peers[j] = sp

    need = set(range(0, id_))
    deadline = time.time() + timeout
    while need:
        if time.time() > deadline:
            server.close()
            for sp in peers.values(): sp.close()
            raise TimeoutError("accept timeout")
        try:
            conn, _ = server.accept()
            tune_socket(conn, sndbuf=sndbuf_mb*1024*1024, rcvbuf=rcvbuf_mb*1024*1024)
            sp = StreamPeer(conn)
            hello = sp.recv()
            j = int(hello["hello"])
            if j not in need:
                sp.close(); continue
            peers[j] = sp
            need.remove(j)
        except socket.timeout:
            pass

    server.close()
    return peers

# ========================= Online 阶段（NumPy 矢量化） =========================
def one_mult_online_vec(pid, peers, seed_prefix, n=1024):
    def s(lbl, subset): return sgen(seed_prefix, lbl, subset, n)

    m        = s("r",  "m")
    y        = s("r2", "m2")         # 可独立种子，避免偶然相等
    lambda1  = s("l1", "l1")
    lambda2  = s("l2", "l2")
    lambday1 = s("ly1","l1")
    lambday2 = s("ly2","l2")
    lambda_s1= s("ls1","ls1")
    lambda_s2= s("ls2","ls2")

    r013 = lambdac1 = lambdac2 = r123 = lambdac_star = None
    lambdac = m03 = m3 = None

    if pid in (0,1,3):
        r013      = s("r013","013")
        lambdac1  = s("lc1","013")
    if pid in (0,2,3):
        lambdac2  = s("lc2","023")
    if pid in (1,2,3):
        r123         = s("r123","123")
        lambdac_star = s("lcs","123")
    if pid in (0,3):
        lambdac = s("lc","03")
        m03 = addp_vec(addp_vec(lambdac, mulp_vec(lambda1, lambda2)),
                       (r013 if r013 is not None else np.zeros(n, np.uint64)))
    if pid == 3:
        tmp = subp_vec(lambda2, lambda_s2)
        m3  = addp_vec(subp_vec(mulp_vec(lambda1, tmp), mulp_vec(lambda2, lambda_s1)),
                       addp_vec(r123, (P - lambdac_star) % (P+1)))

    if pid == 0:
        v0  = addp_vec(mulp_vec(m, lambda1), mulp_vec(y, lambday1))
    if pid in (1,2):
        v12 = mulp_vec(m, y)
    if pid == 1:
        m1  = addp_vec(addp_vec(mulp_vec(m, lambda1), mulp_vec(y, lambday1)), r013)
    if pid == 2:
        m2  = subp_vec(addp_vec(mulp_vec(m, lambda2), mulp_vec(y, lambday2)), m03)
    if pid in (1,2):
        m12 = addp_vec(v12, r123)
    if pid == 1:
        v1  = subp_vec(v12, m1)
    if pid == 2:
        v2  = subp_vec(v12, m2)

    # 交换
    if pid == 1:
        peers[2].send({"tag":"m1", "v": m1})
        m2 = peers[2].recv()["v"]
    elif pid == 2:
        m1 = peers[1].recv()["v"]
        peers[1].send({"tag":"m2", "v": m2})
        peers[0].send({"tag":"m12", "v": m12})
    elif pid == 0:
        m12 = peers[2].recv()["v"]

    if pid == 1:
        return addp_vec(subp_vec(v1, m2), lambdac_star)
    elif pid == 2:
        return addp_vec(subp_vec(v2, m1), lambdac_star)
    elif pid == 0:
        return addp_vec(subp_vec(m12, addp_vec(v0, m03)), lambdac)
    else:
        return np.zeros(n, dtype=np.uint64)

# ========================= main =========================
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
    mc = one_mult_online_vec(pid, peers, args.seed, n=args.batch)
    t1 = time.perf_counter()

    print(f"[P{pid}] batch={args.batch}, total={t1-t0:.3f}s, per-op={(t1-t0)*1000.0:.3f}ms")

    for sp in peers.values():
        sp.close()

if __name__ == "__main__":
    main()
