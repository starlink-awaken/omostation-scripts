#!/bin/bash
# BOS URI Performance Baseline
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== BOS Performance Baseline ==="
echo ""

# 1. Router resolve speed
echo "1. BOSRouter resolve (1000 iterations)"
python3 -c "
import sys, time
sys.path.insert(0, 'projects/agora/src')
from agora.mcp.bos_router import BOSRouter
r = BOSRouter()
r.register('bos://memory/kos/', 'poc')
r.register('bos://memory/kos/search', 'poc')
start = time.time()
for _ in range(1000):
    r.resolve('bos://memory/kos/search')
elapsed = (time.time() - start) * 1000
print(f'   1000 resolves: {elapsed:.1f}ms ({elapsed/1000:.3f}ms avg)')
"

# 2. Cache performance
echo ""
echo "2. Cache hit/miss"
python3 -c "
import sys, time
sys.path.insert(0, 'projects/agora/src')
from agora.mcp.bos_middleware import Cache
c = Cache()
c.set('bos://test', {'q': 'hello'}, 'world', 999)
start = time.time()
for _ in range(10000):
    c.get('bos://test', {'q': 'hello'})
print(f'   10000 cache hits: {(time.time()-start)*1000:.1f}ms')
"

# 3. Rate limiter throughput
echo ""
echo "3. Rate limiter throughput"
python3 -c "
import sys, time
sys.path.insert(0, 'projects/agora/src')
from agora.mcp.bos_middleware import RateLimiter
rl = RateLimiter(default_qps=10000)
passed = 0
start = time.time()
for _ in range(100000):
    if rl.acquire('bos://test'):
        passed += 1
elapsed = time.time() - start
print(f'   {passed}/{100000} passed in {elapsed:.2f}s ({passed/elapsed:.0f} ops/s)')
"

echo ""
echo "=== Baseline complete ==="
