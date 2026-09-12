# MCP Phase 6: Docker Compose - Real Multi-Service Topology ✓ COMPLETE

## The Core Problem This Phase Had to Solve

Phases 2-5 all used **stdio transport**: the client spawns the server as a
*child process on the same host*. That's fundamentally incompatible with
"each MCP server is its own separate container" - you can't stdio-spawn a
process that's supposed to already be running in a different container.
Making each server genuinely independent required a network-based
transport instead.

## What We Built

- **`app/mcp_clients/bridge.py`** now supports two transports behind the
  same `call_mcp_tool()` call site:
  - `server_script=...` → stdio (unchanged since Phase 2, local dev)
  - `server_url=...` → **streamable-http** (new) - confirmed via the
    installed SDK source that `streamable_http_client(url)` returns the
    identical `(read_stream, write_stream)` shape `stdio_client()` does,
    so `ClientSession`/`call_tool` usage is completely unchanged - only
    connection establishment differs.
- **`mcp_servers/_run.py`** - shared entrypoint helper: `MCP_TRANSPORT` env
  var picks stdio (default) or `streamable-http` (host `0.0.0.0`, so the
  container is reachable by service name from other Compose services).
  All three servers' `if __name__ == "__main__":` blocks now just call
  `run_server(server, default_port=...)`.
- **Each agent** (`style_agent.py`, `security_agent.py`,
  `test_coverage_agent.py`) checks a `*_MCP_URL` env var first, falling
  back to the local stdio path if unset - same pattern as `REDIS_HOST`
  defaulting to `localhost` since Phase 7.
- **`docker-compose.yml`**: three new services (`linter-server`,
  `test-coverage-server`, `security-server`), each built from the same
  image as `app` (they need the same code + deps) but running a different
  server script with `MCP_TRANSPORT=http`. `app`'s environment now points
  `LINTER_MCP_URL`/`TEST_COVERAGE_MCP_URL`/`SECURITY_MCP_URL` at each
  service's internal `http://<service-name>:<port>/mcp` address.
- **`Dockerfile`**: now also copies `mcp_servers/` (previously only
  `app/`), since all four services share one image.

## Verified End-to-End on the Real 5-Container Stack

`docker compose up -d --build` → all 5 containers (`app`, `redis`,
`linter-server`, `test-coverage-server`, `security-server`) started
healthy.

A real review through `POST /review` → `GET /review/{id}` produced a
correct, coherent merged result - and the **MCP server containers'
own logs confirm genuine network traffic**, not a silent fallback:

```
linter-server-1  | Created new transport with session ID: 0d7db7f2...
linter-server-1  | INFO: 172.19.0.6:50328 - "POST /mcp HTTP/1.1" 200 OK
linter-server-1  | INFO: 172.19.0.6:50338 - "GET /mcp HTTP/1.1" 200 OK
linter-server-1  | INFO: 172.19.0.6:50342 - "POST /mcp HTTP/1.1" 202 Accepted
linter-server-1  | INFO: 172.19.0.6:50354 - "POST /mcp HTTP/1.1" 200 OK
linter-server-1  | Terminating session: 0d7db7f2...
```

`172.19.0.6` is the `app` container's IP on the Compose network - a full
MCP session lifecycle (create → handshake → tool call → terminate)
genuinely crossing container boundaries. Identical confirmed for
`security-server` and `test-coverage-server`.

**Phase 7's cache still works correctly in this topology**: submitting
the same diff twice returned the identical result in 190ms with an
explicit `"Cache hit"` log line - caching, tracing, and the MCP refactor
all compose correctly together.

## Known Cosmetic Detail (Not a Bug)

`docker compose ps` shows all three MCP-server containers as `8000/tcp`
in the PORTS column - that's the shared image's `EXPOSE 8000` (baked in
for `app`'s benefit) being inherited, not the servers' actual listening
ports. The logs confirm each one is genuinely listening on its real
configured port (8001/8002/8003); `EXPOSE` is Docker metadata only and
doesn't affect routing. Not worth four separate Dockerfiles to fix a
cosmetic `ps` column.

## Files Created/Modified

- `mcp_servers/_run.py` (new)
- `mcp_servers/linter_server.py`, `test_coverage_server.py`,
  `security_server.py` (entrypoint swapped to use `run_server()`)
- `app/mcp_clients/bridge.py` (added HTTP transport)
- `app/agents/style_agent.py`, `security_agent.py`,
  `test_coverage_agent.py` (added `*_MCP_URL` env-var check)
- `docker-compose.yml` (3 new services, `app`'s env vars + depends_on)
- `Dockerfile` (now also copies `mcp_servers/`)

## Next: MCP Phase 7 - Re-run Eval + Update README

Re-run the original build's Phase 6 eval script against the same locked
eval slice, to confirm the MCP refactor didn't change review quality
versus the pre-refactor baseline - then write up the before/after
architecture description.
