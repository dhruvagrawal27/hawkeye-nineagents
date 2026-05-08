// HAWKEYE Neo4j schema init.
// Idempotent — applied via docker-compose at startup, or manually via:
//   docker compose exec neo4j cypher-shell -u neo4j -p $NEO4J_PASS -f /init.cypher

CREATE CONSTRAINT employee_id IF NOT EXISTS FOR (e:Employee) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT system_id   IF NOT EXISTS FOR (s:System)   REQUIRE s.id IS UNIQUE;
CREATE INDEX     employee_score_idx   IF NOT EXISTS FOR (e:Employee) ON (e.risk_score);
CREATE INDEX     employee_dept_idx    IF NOT EXISTS FOR (e:Employee) ON (e.department);
