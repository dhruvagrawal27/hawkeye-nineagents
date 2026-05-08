"""Neo4j graph service.

Schema:
  (:Employee {id, account_id, risk_score, risk_level, department, last_seen_at})
  (:System   {id, kind, access_count})
  (Employee)-[:ACCESSED {count, last_at, write_count, read_count}]->(System)

The consumer issues an upsert per event. The /graph/* endpoints query for
neighbourhoods, hubs, and (for the "collusion clusters" UI) connected
employees via shared systems.
"""

from __future__ import annotations

from typing import Any

import structlog
from neo4j import AsyncGraphDatabase

from app.config import settings

log = structlog.get_logger(__name__)


CONSTRAINTS = [
    "CREATE CONSTRAINT employee_id IF NOT EXISTS FOR (e:Employee) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT system_id   IF NOT EXISTS FOR (s:System)   REQUIRE s.id IS UNIQUE",
    "CREATE INDEX     employee_score_idx IF NOT EXISTS FOR (e:Employee) ON (e.risk_score)",
]


class GraphService:
    def __init__(self) -> None:
        self._driver = None

    async def connect(self) -> None:
        if self._driver is not None:
            return
        self._driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASS),
        )
        await self._driver.verify_connectivity()
        async with self._driver.session() as s:
            for stmt in CONSTRAINTS:
                await s.run(stmt)
        log.info("graph.connected", uri=settings.NEO4J_URI)

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    async def _session(self):
        if self._driver is None:
            await self.connect()
        assert self._driver is not None
        return self._driver.session()

    async def upsert_event(
        self,
        *,
        employee_id: str,
        account_id: str,
        system_id: str,
        access_type: str,
        ts: str,
    ) -> None:
        cypher = """
        MERGE (e:Employee {id: $emp})
          ON CREATE SET e.account_id = $acct, e.risk_score = 0.0, e.risk_level = 'LOW'
        SET e.last_seen_at = $ts
        MERGE (s:System {id: $sys})
          ON CREATE SET s.kind = 'core_banking', s.access_count = 0
        SET s.access_count = coalesce(s.access_count, 0) + 1
        MERGE (e)-[r:ACCESSED]->(s)
          ON CREATE SET r.count = 0, r.read_count = 0, r.write_count = 0
        SET r.count = r.count + 1,
            r.last_at = $ts,
            r.read_count  = r.read_count  + CASE WHEN $access = 'READ'  THEN 1 ELSE 0 END,
            r.write_count = r.write_count + CASE WHEN $access = 'WRITE' THEN 1 ELSE 0 END
        """
        async with await self._session() as s:
            await s.run(
                cypher,
                emp=employee_id,
                acct=account_id,
                sys=system_id,
                access=access_type or "READ",
                ts=ts,
            )

    async def update_employee_score(
        self,
        *,
        employee_id: str,
        account_id: str,
        score: float,
        risk_level: str,
        department: str | None = None,
    ) -> None:
        cypher = """
        MERGE (e:Employee {id: $emp})
        SET e.account_id = $acct,
            e.risk_score = $score,
            e.risk_level = $level,
            e.department = coalesce($department, e.department)
        """
        async with await self._session() as s:
            await s.run(cypher, emp=employee_id, acct=account_id, score=float(score), level=risk_level, department=department)

    async def neighbourhood(self, employee_id: str, depth: int = 2) -> dict[str, Any]:
        depth = max(1, min(int(depth), 3))
        cypher = f"""
        MATCH (root:Employee {{id: $emp}})
        OPTIONAL MATCH path = (root)-[:ACCESSED*1..{depth}]-(other)
        WITH root, collect(distinct path) AS paths
        UNWIND paths AS p
        WITH root, nodes(p) AS ns, relationships(p) AS rs
        UNWIND ns AS n
        WITH root, collect(distinct n) AS allNodes, rs
        UNWIND rs AS r
        RETURN
          [n IN allNodes | {{
            id: n.id,
            label: head(labels(n)),
            risk_score: coalesce(n.risk_score, 0.0),
            risk_level: coalesce(n.risk_level, 'LOW'),
            kind: coalesce(n.kind, null),
            department: coalesce(n.department, null),
            access_count: coalesce(n.access_count, null)
          }}] AS nodes,
          collect(distinct {{
            source: startNode(r).id,
            target: endNode(r).id,
            count: r.count,
            last_at: toString(r.last_at)
          }}) AS edges
        """
        async with await self._session() as s:
            result = await s.run(cypher, emp=employee_id)
            record = await result.single()
            if record is None:
                return {"nodes": [], "edges": []}
            return {"nodes": record["nodes"] or [], "edges": record["edges"] or []}

    async def top_risk_subgraph(self, min_score: float = 0.16, limit_employees: int = 200) -> dict[str, Any]:
        cypher = """
        MATCH (e:Employee)
        WHERE e.risk_score >= $min_score
        WITH e ORDER BY e.risk_score DESC LIMIT $limit
        OPTIONAL MATCH (e)-[r:ACCESSED]->(s:System)
        WITH collect(distinct e) AS emps, collect(distinct s) AS sysxs, collect({src: e.id, dst: s.id, count: r.count}) AS rels
        RETURN
          [n IN emps | {id: n.id, label: 'Employee', risk_score: n.risk_score, risk_level: n.risk_level, department: n.department, kind: null, access_count: null}] +
          [n IN sysxs | {id: n.id, label: 'System', risk_score: 0.0, risk_level: 'LOW', department: null, kind: n.kind, access_count: n.access_count}] AS nodes,
          [r IN rels | {source: r.src, target: r.dst, count: r.count, last_at: null}] AS edges
        """
        async with await self._session() as s:
            result = await s.run(cypher, min_score=float(min_score), limit=int(limit_employees))
            record = await result.single()
            if record is None:
                return {"nodes": [], "edges": []}
            return {"nodes": record["nodes"] or [], "edges": record["edges"] or []}

    async def hubs(self, top_n: int = 10) -> list[dict[str, Any]]:
        cypher = """
        MATCH (s:System)<-[r:ACCESSED]-(e:Employee)
        WHERE e.risk_score >= $min_score
        WITH s, count(distinct e) AS flagged_users, collect(e.id) AS users
        ORDER BY flagged_users DESC
        LIMIT $top_n
        RETURN s.id AS system_id, flagged_users, users[0..10] AS sample_users
        """
        async with await self._session() as s:
            result = await s.run(cypher, min_score=0.16, top_n=int(top_n))
            return [r.data() async for r in result]

    async def shared_systems(self, employee_id: str) -> list[dict[str, Any]]:
        """For the narrative service — how many systems does this employee share with other flagged employees, and how many flagged peers?"""
        cypher = """
        MATCH (e:Employee {id: $emp})-[:ACCESSED]->(s:System)<-[:ACCESSED]-(other:Employee)
        WHERE other.id <> $emp AND coalesce(other.risk_score, 0) >= $min_score
        WITH s, collect(distinct other.id) AS peers
        RETURN s.id AS system_id, peers
        """
        async with await self._session() as s:
            result = await s.run(cypher, emp=employee_id, min_score=0.16)
            return [r.data() async for r in result]

    async def health(self) -> bool:
        try:
            if self._driver is None:
                await self.connect()
            assert self._driver is not None
            async with self._driver.session() as s:
                await s.run("RETURN 1")
            return True
        except Exception as exc:
            log.warning("graph.health_check_failed", error=str(exc))
            return False


graph_service = GraphService()
