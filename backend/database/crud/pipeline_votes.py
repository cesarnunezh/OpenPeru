from __future__ import annotations

from sqlalchemy import select, delete, func, case, literal, or_, and_

from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from backend import LegPeriod, TypeOrganization, AttendanceStatus, TypeRoleBill
from backend.database import models as db_models
from backend.core.parsers import LEG_PERIOD_RANGES


def find_leg_period_expr(value_col: ColumnElement) -> ColumnElement:
    """
    SQLAlchemy expression version.
    Use this inside select(), group_by(), where(), joins, etc.
    """
    value_date = func.date(value_col)

    return case(
        *[
            (
                (value_date >= start_date.isoformat())
                & (value_date <= end_date.isoformat()),
                literal(leg_period.value),
            )
            for leg_period, start_date, end_date in LEG_PERIOD_RANGES
        ],
        else_=literal(LegPeriod.PERIODO_1992_1995.value),
    )


def refresh_congresista_metrics(db: Session) -> int:
    """
    Rebuild congresista_metrics from the existing processed tables.

    This function deletes and recreates all rows in congresista_metrics.
    It does not commit. The caller must run it inside a transaction.
    """

    db.execute(delete(db_models.CongresistaMetric))

    attendance_sq = (
        select(
            db_models.Attendance.attendee_id.label("cong_id"),
            db_models.ChamberMembership.leg_period.label("leg_period"),
            func.avg(
                case(
                    (
                        db_models.Attendance.status == AttendanceStatus.PRESENTE,
                        1.0,
                    ),
                    else_=0.0,
                )
            ).label("avg_attendance"),
        )
        .join(
            db_models.VoteEvent,
            db_models.VoteEvent.vote_event_id == db_models.Attendance.event_id,
        )
        .join(
            db_models.ChamberMembership,
            and_(
                db_models.ChamberMembership.person_id
                == db_models.Attendance.attendee_id,
                db_models.ChamberMembership.org_id == db_models.VoteEvent.org_id,
                db_models.ChamberMembership.org_type == TypeOrganization.CHAMBER,
                db_models.VoteEvent.event_date
                >= db_models.ChamberMembership.start_date,
                or_(
                    db_models.ChamberMembership.end_date.is_(None),
                    db_models.VoteEvent.event_date
                    <= db_models.ChamberMembership.end_date,
                ),
            ),
        )
        .group_by(
            db_models.Attendance.attendee_id,
            db_models.ChamberMembership.leg_period,
        )
        .subquery()
    )

    bill_dates_sq = (
        select(
            db_models.BillOrganization.bill_id.label("bill_id"),
            func.min(db_models.BillOrganization.presentation_date).label(
                "presentation_date"
            ),
        )
        .group_by(db_models.BillOrganization.bill_id)
        .subquery()
    )

    bills_sq = (
        select(
            db_models.BillCongresistas.person_id.label("cong_id"),
            find_leg_period_expr(bill_dates_sq.c.presentation_date).label("leg_period"),
            func.count(db_models.BillCongresistas.bill_id).label("bills_auth"),
            func.avg(
                case(
                    (db_models.Bill.bill_approved.is_(True), 1.0),
                    else_=0.0,
                )
            ).label("bills_success_rate"),
        )
        .join(db_models.Bill, db_models.Bill.id == db_models.BillCongresistas.bill_id)
        .join(bill_dates_sq, bill_dates_sq.c.bill_id == db_models.Bill.id)
        .where(db_models.BillCongresistas.role_type == TypeRoleBill.AUTHOR)
        .group_by(
            db_models.BillCongresistas.person_id,
            find_leg_period_expr(bill_dates_sq.c.presentation_date),
        )
        .subquery()
    )

    motion_dates_sq = (
        select(
            db_models.MotionOrganization.motion_id.label("motion_id"),
            func.min(db_models.MotionOrganization.presentation_date).label(
                "presentation_date"
            ),
        )
        .group_by(db_models.MotionOrganization.motion_id)
        .subquery()
    )

    motions_sq = (
        select(
            db_models.MotionCongresistas.person_id.label("cong_id"),
            find_leg_period_expr(motion_dates_sq.c.presentation_date).label(
                "leg_period"
            ),
            func.count(db_models.MotionCongresistas.motion_id).label("motions_auth"),
            func.avg(
                case(
                    (db_models.Motion.motion_approved.is_(True), 1.0),
                    else_=0.0,
                )
            ).label("motions_success_rate"),
        )
        .join(
            db_models.Motion,
            db_models.Motion.id == db_models.MotionCongresistas.motion_id,
        )
        .join(motion_dates_sq, motion_dates_sq.c.motion_id == db_models.Motion.id)
        .where(db_models.MotionCongresistas.role_type == TypeRoleBill.AUTHOR)
        .group_by(
            db_models.MotionCongresistas.person_id,
            find_leg_period_expr(motion_dates_sq.c.presentation_date),
        )
        .subquery()
    )

    camara_memberships_sq = (
        select(
            db_models.ChamberMembership.person_id.label("cong_id"),
            db_models.ChamberMembership.leg_period.label("leg_period"),
        )
        .where(db_models.ChamberMembership.org_type == TypeOrganization.CHAMBER)
        .distinct()
        .subquery()
    )

    rows = db.execute(
        select(
            camara_memberships_sq.c.cong_id,
            camara_memberships_sq.c.leg_period,
            attendance_sq.c.avg_attendance,
            func.coalesce(bills_sq.c.bills_auth, 0).label("bills_auth"),
            bills_sq.c.bills_success_rate,
            func.coalesce(motions_sq.c.motions_auth, 0).label("motions_auth"),
            motions_sq.c.motions_success_rate,
        )
        .outerjoin(
            attendance_sq,
            (attendance_sq.c.cong_id == camara_memberships_sq.c.cong_id)
            & (attendance_sq.c.leg_period == camara_memberships_sq.c.leg_period),
        )
        .outerjoin(
            bills_sq,
            (bills_sq.c.cong_id == camara_memberships_sq.c.cong_id)
            & (bills_sq.c.leg_period == camara_memberships_sq.c.leg_period),
        )
        .outerjoin(
            motions_sq,
            (motions_sq.c.cong_id == camara_memberships_sq.c.cong_id)
            & (motions_sq.c.leg_period == camara_memberships_sq.c.leg_period),
        )
    ).all()

    metrics = [
        db_models.CongresistaMetric(
            cong_id=row.cong_id,
            leg_period=row.leg_period,
            avg_attendance=row.avg_attendance,
            bills_auth=row.bills_auth,
            bills_success_rate=row.bills_success_rate,
            motions_auth=row.motions_auth,
            motions_success_rate=row.motions_success_rate,
        )
        for row in rows
    ]

    db.add_all(metrics)
    db.flush()

    return len(metrics)
