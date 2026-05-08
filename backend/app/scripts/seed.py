"""Seed script — populate Postgres + Redis + Neo4j from the artifacts.

Idempotent. Safe to re-run. Skips inserts when data already present.

Run from container:  python -m app.scripts.seed
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import structlog
from sqlalchemy import func, select

from app.config import settings
from app.logging_setup import configure_logging
from app.models.alert import Alert
from app.models.db import get_session, init_engine
from app.models.employee import Employee, ScoreHistory
from app.services.feature_aggregator import feature_aggregator
from app.services.graph_service import graph_service
from app.services.risk_levels import score_to_display, score_to_level
from app.services.scoring import scoring_service

log = structlog.get_logger(__name__)


_FIRST_NAMES = [
    "Aarav", "Arjun", "Aditya", "Ananya", "Avani", "Bhavna", "Chetan", "Deepak",
    "Devika", "Dhruv", "Esha", "Falguni", "Gaurav", "Geeta", "Harsh", "Ishaan",
    "Jaya", "Kabir", "Kavita", "Krishna", "Lakshmi", "Madhav", "Manish", "Meera",
    "Naveen", "Neha", "Omkar", "Parul", "Pranav", "Priya", "Rahul", "Rajesh",
    "Ravi", "Riya", "Rohit", "Sahil", "Sandeep", "Sanjay", "Shreya", "Siddharth",
    "Sonali", "Sunil", "Suresh", "Tarun", "Uma", "Varsha", "Vijay", "Vikram",
    "Vishal", "Yash",
]
_LAST_NAMES = [
    "Agarwal", "Bansal", "Bhat", "Chatterjee", "Chowdhury", "Das", "Dey",
    "Gupta", "Iyer", "Jain", "Joshi", "Kapoor", "Kaur", "Khanna", "Kumar",
    "Malhotra", "Mehta", "Mishra", "Nair", "Pandey", "Patel", "Pillai",
    "Rao", "Reddy", "Saxena", "Sharma", "Shetty", "Singh", "Srinivasan",
    "Tiwari", "Verma",
]
_DEPARTMENTS = ["Core Banking", "Treasury", "Loans", "HRMS", "Compliance"]


def _name_for(employee_id: str) -> str:
    h = int(hashlib.sha256(employee_id.encode()).hexdigest(), 16)
    f = _FIRST_NAMES[h % len(_FIRST_NAMES)]
    last = _LAST_NAMES[(h // 1000) % len(_LAST_NAMES)]
    return f"{f} {last}"


def _department_for(employee_id: str) -> str:
    h = int(hashlib.sha256(employee_id.encode()).hexdigest(), 16)
    return _DEPARTMENTS[h % len(_DEPARTMENTS)]


def _to_employee_id(account_id: str) -> str:
    if account_id.startswith("ACC_"):
        return "EMP_" + account_id[4:]
    if account_id.startswith("ACCT_"):
        return "EMP_" + account_id[5:]
    return f"EMP_{account_id}"


async def seed_alerts_and_employees() -> dict[str, int]:
    """Pre-populate Postgres with 50 alerts + corresponding employees from
    the top-50 highest-scoring real-mule rows. Idempotent: re-running with
    >=10 alerts is a no-op.

    Memory-aware: read only id + oof_proba first to find the top 50, then
    re-read only those rows with full feature columns. This keeps peak RAM
    well below the matrix's 200MB+ in-memory footprint.
    """
    matrix_path = settings.artifacts_path / "account_feature_matrix.parquet"
    if not matrix_path.exists():
        log.warning("seed.matrix_missing", path=str(matrix_path))
        return {"alerts": 0, "employees": 0}

    inserted_alerts = 0
    inserted_employees = 0

    async for db in get_session():
        existing = await db.scalar(select(func.count(Alert.id))) or 0
        if existing >= 10:
            log.info("seed.alerts_already_present", count=int(existing))
            return {"alerts": int(existing), "employees": 0}

        # Stage 1: small read — only ids + label + score
        ids = pd.read_parquet(matrix_path, columns=["account_id", "is_mule", "oof_proba"])
        top_mules = ids[ids["is_mule"] == 1].nlargest(40, "oof_proba")
        edge_legits = ids[ids["is_mule"] == 0].nlargest(10, "oof_proba")
        sample_ids = pd.concat([top_mules, edge_legits])["account_id"].tolist()
        del ids, top_mules, edge_legits

        # Stage 2: read full feature rows only for the 50 selected ids
        df = pd.read_parquet(
            matrix_path,
            columns=["account_id", "is_mule", "oof_proba", *scoring_service.feat_cols],
            filters=[("account_id", "in", sample_ids)],
        )
        sample = df.reset_index(drop=True)
        del df

        threshold = scoring_service.threshold

        for _, row in sample.iterrows():
            account_id = str(row["account_id"])
            employee_id = _to_employee_id(account_id)

            features = {c: row[c] for c in scoring_service.feat_cols}
            score_result = scoring_service.score(features, k_factors=5)

            # Override raw score with the matrix.oof_proba so we don't double-pay
            # for any rounding error between training and runtime.
            raw = float(row["oof_proba"])
            display = score_to_display(raw, threshold)
            level = score_to_level(raw, threshold)
            is_alert = raw >= threshold

            # Always seed the employee row
            existing_emp = await db.get(Employee, employee_id)
            if existing_emp is None:
                db.add(
                    Employee(
                        id=employee_id,
                        account_id=account_id,
                        display_name=_name_for(employee_id),
                        department=_department_for(employee_id),
                        is_mule_seed=int(row["is_mule"]),
                    )
                )
                inserted_employees += 1

            # Seed score history points (a few across the last 30 days)
            now = datetime.now(timezone.utc)
            random.seed(hash(employee_id) & 0xFFFFFFFF)
            for d_back in (28, 21, 14, 7, 3, 1):
                wobble = random.uniform(-0.015, 0.015)
                point_score = max(0.0, raw + wobble)
                db.add(
                    ScoreHistory(
                        employee_id=employee_id,
                        score=point_score,
                        display_score=score_to_display(point_score, threshold),
                        recorded_at=now - timedelta(days=d_back),
                    )
                )

            if not is_alert:
                continue

            hours_ago = random.uniform(0.5, 72)
            triggered_at = now - timedelta(hours=hours_ago)
            db.add(
                Alert(
                    employee_id=employee_id,
                    account_id=account_id,
                    score=raw,
                    display_score=display,
                    risk_level=level,
                    status="open",
                    triggered_at=triggered_at,
                    last_seen_at=triggered_at,
                    shap_factors=[f.to_dict() for f in score_result.factors],
                    top_signal=score_result.factors[0].name_human if score_result.factors else None,
                    source="seed",
                )
            )
            inserted_alerts += 1

        await db.commit()

    log.info("seed.alerts_done", inserted_alerts=inserted_alerts, inserted_employees=inserted_employees)
    return {"alerts": inserted_alerts, "employees": inserted_employees}


async def seed_redis_features() -> int:
    """Snapshot synthetic-account base features into Redis so the consumer
    can score events for them.

    Memory-aware: pick a small donor pool (300 mules + 1000 legits), keep
    only those feature rows in RAM, then iterate the synthetic accounts and
    pick a donor by hash. Avoids holding the full 160k-row matrix in memory.
    """
    accounts_path = settings.data_path / "synthetic_accounts.parquet"
    matrix_path = settings.artifacts_path / "account_feature_matrix.parquet"
    if not accounts_path.exists() or not matrix_path.exists():
        log.warning("seed.feature_files_missing", accounts=str(accounts_path), matrix=str(matrix_path))
        return 0

    # Stage 1 — small read: pick donor account ids
    ids = pd.read_parquet(matrix_path, columns=["account_id", "is_mule", "oof_proba"])
    mule_ids = ids[ids["is_mule"] == 1].nlargest(300, "oof_proba")["account_id"].tolist()
    legit_ids = ids[ids["is_mule"] == 0].sample(n=min(1000, len(ids[ids["is_mule"] == 0])), random_state=0)["account_id"].tolist()
    del ids

    # Stage 2 — read only donor feature rows
    donor_pool_ids = mule_ids + legit_ids
    donors_df = pd.read_parquet(
        matrix_path,
        columns=["account_id", "is_mule", *scoring_service.feat_cols],
        filters=[("account_id", "in", donor_pool_ids)],
    )
    donors_df = donors_df.set_index("account_id")
    real_mule_ids = donors_df[donors_df["is_mule"] == 1].index.tolist()
    real_legit_ids = donors_df[donors_df["is_mule"] == 0].index.tolist()

    await feature_aggregator.connect()
    sa = pd.read_parquet(accounts_path, columns=["account_id", "is_mule"])

    n = 0
    for _, srow in sa.iterrows():
        synth_id = str(srow["account_id"])
        is_mule = int(srow["is_mule"])
        pool = real_mule_ids if is_mule else real_legit_ids
        if not pool:
            continue
        h = int(hashlib.sha256(synth_id.encode()).hexdigest(), 16)
        chosen = pool[h % len(pool)]
        feature_row = donors_df.loc[chosen]
        features = {c: feature_row[c] for c in scoring_service.feat_cols}
        await feature_aggregator.store_base_features(synth_id, features)
        n += 1
        if n % 2000 == 0:
            log.info("seed.redis_progress", stored=n)
    log.info("seed.redis_done", stored=n)
    return n


async def seed_neo4j_graph() -> int:
    """Initialise the graph with seeded employees so /graph is non-empty
    even before replay starts. We add an :Employee per seeded alert and
    a few representative :System nodes."""
    await graph_service.connect()

    n = 0
    async for db in get_session():
        employees = (await db.execute(select(Employee).limit(120))).scalars().all()
        for emp in employees:
            score = 0.0
            level = "LOW"
            latest = (
                await db.execute(
                    select(ScoreHistory)
                    .where(ScoreHistory.employee_id == emp.id)
                    .order_by(ScoreHistory.recorded_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if latest is not None:
                score = float(latest.score)
                level = score_to_level(score, scoring_service.threshold)

            await graph_service.update_employee_score(
                employee_id=emp.id,
                account_id=emp.account_id,
                score=score,
                risk_level=level,
                department=emp.department,
            )
            # Each employee touches 2-4 representative systems for an interesting graph
            random.seed(hash(emp.id) & 0xFFFFFFFF)
            n_sys = random.randint(2, 4)
            for k in range(n_sys):
                # Mix shared "hub" systems and per-employee unique systems
                if k == 0:
                    sys_id = f"SYS_HUB_{(hash(emp.id) % 5):02d}"
                else:
                    sys_id = f"SYS_{(hash(emp.id) + k) & 0xFFFFFF:06d}"
                await graph_service.upsert_event(
                    employee_id=emp.id,
                    account_id=emp.account_id,
                    system_id=sys_id,
                    access_type="WRITE" if score > scoring_service.threshold else "READ",
                    ts=datetime.now(timezone.utc).isoformat(),
                )
            n += 1
    log.info("seed.neo4j_done", employees=n)
    return n


async def main() -> None:
    configure_logging()
    init_engine()
    scoring_service.load()
    # Warm SHAP with a small background (50 rows) so seeded alerts have factors.
    # The running backend already has its own SHAP explainer with a larger
    # background (200 rows); this is just for the seed run.
    try:
        scoring_service.warm_shap(background_rows=50)
    except Exception as exc:
        log.warning("seed.shap_warm_failed", error=str(exc))

    a = await seed_alerts_and_employees()
    r = await seed_redis_features()
    g = await seed_neo4j_graph()

    log.info("seed.complete", alerts=a, redis_features=r, neo4j_employees=g)
    print(json.dumps({"alerts": a, "redis_features": r, "neo4j_employees": g}, default=str))


if __name__ == "__main__":
    asyncio.run(main())
